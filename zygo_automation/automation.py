from itertools import product
import glob as glob
import os
from time import sleep

import h5py
import numpy as np

from .zygo import capture_frame, read_many_raw_datx
from .dm import load_channel, set_pixel, set_row_column, write_fits

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def Zygo_DM_Run(dm_inputs, network_path, outname, dry_run=False):
    '''
    Loop over dm_inputs, setting the DM in the requested state,
    and taking measurements on the Zygo.

    In the outname directory, the individual measurements are
    saved in separate .datx files. Consolidated measurements
    (surface maps, intensity maps, attributes, dm inputs) are
    saved out to 'alldata.hdf5' under this direcotry.

    Parameters:
        dm_inputs: array-like
            Cube of displacement images. The DM will iteratively
            be set in each state on channel 0.
        network_path : str
            Path to shared network folder visible to both
            Corona and the Zygo machine. This is where
            cross-machine communication will take place.
            Both machines must have read/write privileges.
        outname : str
            Directory to write results out to. Directory
            must not already exist.
        dry_run : bool, opt.
            If toggled to True, this will loop over DM states
            without taking images. This is useful to debugging
            things on the DM side / watching the fringes on
            the Zygo live monitor.
    Returns: nothing

    '''
    if not dry_run:
        # Create a new directory outname to save results to
        assert not os.path.exists(outname), '{} already exists!'.format(outname)
        os.mkdir(outname)

    for idx, inputs in enumerate(dm_inputs):
        #Remove any old inputs if they exist
        old_files = glob.glob(os.path.join(network_path,'dm_input*.fits'))
        for old_file in old_files:
            if os.path.exists(old_file):
                os.remove(old_file)

        # Write out FITS file with requested DM input
        log.info('Setting DM to state {}/{}.'.format(idx + 1, len(dm_inputs)))
        input_file = os.path.join(network_path,'dm_input.fits'.format(idx))
        write_fits(input_file, inputs, overwrite=True)

        # Wait until DM indicates it's in the requested state
        # I'm a little worried the DM could get there before
        # the monitor starts watching the dm_ready file, but 
        # that hasn't happened yet.
        zm = ZygoMonitor(network_path)
        zm.watch(0.1)
        log.info('DM ready!')

        if not dry_run:
            # Take an image on the Zygo
            log.info('Taking image!')
            capture_frame(filename=os.path.join(outname,'frame_{0:05d}.datx'.format(idx)))

        # Remove input file
        if os.path.exists(input_file):
            os.remove(input_file)

    log.info('Writing to consolidated .hdf5 file.')
    # Consolidate individual frames and inputs
    # Don't read attributes into a dictionary. This causes python to crash (on Windows)
    # when re-assignging them to hdf5 attributes.
    alldata = read_many_raw_datx(sorted(glob.glob(os.path.join(outname,'frame_*.datx'))), 
                                 attrs_to_dict=False, mask_and_scale=False)
    write_dm_run_to_hdf5(os.path.join(outname,'alldata.hdf5'),
                         np.asarray(alldata['surface']),
                         alldata['surface_attrs'][0],
                         np.asarray(alldata['intensity']),
                         alldata['intensity_attrs'][0],
                         alldata['attrs'][0],
                         np.asarray(dm_inputs),
                         alldata['mask'][0]
                         )

def write_dm_run_to_hdf5(filename, surface_cube, surface_attrs, intensity_cube,
                         intensity_attrs, all_attributes, dm_inputs, mask):
    '''
    Write the measured surface, intensity, attributes, and inputs
    to a single HDF5 file.

    Attempting to write out the Mx dataset attributes (surface, intensity)
    currently breaks things (Python crashes), so I've disabled that for now.
    All the information *should* be in the attributes group, but it's
    not as convenient.

    Parameters:
        filename: str
            File to write out consolidate data to
        surface_cube : nd array
            Cube of surface images
         surface_attrs : dict or h5py attributes object
            Currently not used, but expected.
         intensity_cube : nd array
            Cube of intensity images
        intensity_attrs : dict or h5py attributes object
            Currently not used, but expected
        all_attributes : dict or h5py attributes object
            Mx attributes to associate with the file.
        dm_inputs : nd array
            Cube of inputs for the DM
        mask : nd array
            2D mask image
    Returns: nothing
    '''

    # create hdf5 file
    f = h5py.File(filename)
    
    # surface data and attributes
    surf = f.create_dataset('surface', data=surface_cube)
    #surf.attrs.update(surface_attrs)

    intensity = f.create_dataset('intensity', data=intensity_cube)
    #intensity.attrs.update(intensity_attrs)

    attributes = f.create_group('attributes')
    attributes.attrs.update(all_attributes)

    dm_inputs = f.create_dataset('dm_inputs', data=dm_inputs)
    #dm_inputs.attrs['units'] = 'microns'

    mask = f.create_dataset('mask', data=mask)
    
    f.close()

def test_inputs_pixel(xpix, ypix, val):
    '''
    Generate a list of images looping over
    every actuator on the DM.

    Parameters:
        xpix, ypix: ints
            X and Y dimensions of the DM
        val : float
            Value to set each pixel to.

    Returns:
        image_list : nd array
            list of (ypix, xpix) nd arrays
    '''
    pixel_list = product(range(xpix), range(ypix), [val,] )
    image_list = []
    for pix in pixel_list:
        image_list.append( set_pixel(*pix) )
    return image_list

def test_inputs_row_column(num_cols, val, dim=0):
    '''
    Generate a list of images looping over
    every row/column on the DM.

    Parameters:
        num_cols: int
            Number of rows/columns along
            the axis being looped over
        val : float
            Value to set each row/column to.
        dim : int
            0 or 1. Loop over X or Y dimension.

    Returns:
        image_list : nd array
            list of (ypix, xpix) nd arrays
    '''
            
    image_list = []
    for col in range(num_cols):
        image_list.append( set_row_column(col, val, dim=dim) )
    return image_list

def mask_inputs(xdim, ydim, value):
    '''
    Create the DM inputs necessary for defining
    a mask in Mx.

    This creates two images in which the edges
    of the active mirror are set to plus/minus
    the input value.

    Usage:
    1. Oversize the mask in Mx, feed the
    mask_inputs into Zygo_DM_Run.
    2. Read in the resulting images and 
    difference them.
    3. Set the "real" mask to encompass
    the active part of the DM. 

    Parameters:
        xdim, ydim : int
            X, Y dimensions of DM
        value :
            Amount by which to push/pull
            the edge actuators.

    Returns:
        image_list : list of array-likes
            Cube of images used to define the mask
    '''

    vallist = [-value, value]
    image_list = []
    for val in vallist:
        im1 = set_row_column(0, val, dim=0, xdim=xdim, ydim=ydim)
        im2 = set_row_column(-1, val, dim=0, xdim=xdim, ydim=ydim)
        im3 = set_row_column(0, val, dim=1, xdim=xdim, ydim=ydim)
        im4 = set_row_column(-1, val, dim=1, xdim=xdim, ydim=ydim)
        image = im1 + im2 + im3 + im4
        image_list.append(image)

    return image_list


class FileMonitor(object):
    '''
    Watch a file for modifications at some
    cadence and perform some action when
    it's modified.  
    '''
    def __init__(self, file_to_watch):
        '''
        Parameters:
            file_to_watch : str
                Full path to a file to watch for.
                On detecting a modificiation, do
                something (self.on_new_data)
        '''
        self.file = file_to_watch
        self.continue_monitoring = True

        # Find initial state
        self.last_modified = self.get_last_modified(self.file)

    def watch(self, period=1.):
        '''
        Pick out new data that have appeared since last query.
        Period given in seconds.
        '''
        try:
            while self.continue_monitoring:
                # Check the file
                last_modified = self.get_last_modified(self.file)

                # If it's been modified (and not deleted) perform
                # some action and update the last-modified time.
                if last_modified != self.last_modified:
                    if os.path.exists(self.file):
                        self.on_new_data(self.file)
                    self.last_modified = last_modified

                # Sleep for a bit
                sleep(period)
        except KeyboardInterrupt:
            return

    def get_last_modified(self, file):
        '''
        If the file already exists, get its last
        modified time. Otherwise, set it to 0.
        '''
        if os.path.exists(file):
            last_modified = os.stat(file).st_mtime
        else:
            last_modified = 0.
        return last_modified

    def on_new_data(self, newdata):
        ''' Placeholder '''
        pass

class ZygoMonitor(FileMonitor):
    '''
    Set the Zygo machine to watch for an indication from
    the DM that it's been put in the requested state,
    and proceed with data collection when ready
    '''
    def __init__(self, path):
        '''
        Parameters:
            path : str
                Network path to watch for 'dm_ready'
                file indicating the DM is in the
                requested state.
        '''
        super().__init__(os.path.join(path,'dm_ready'))

    def on_new_data(self, newdata):
        '''
        On detecting a new 'dm_ready' file,
        stop blocking the Zygo code. (No 
        actual image capture happens here.)
        '''
        os.remove(newdata) # delete DM ready file
        self.continue_monitoring = False # stop monitor loop

class DMMonitor(FileMonitor):
    '''
    Set the DM machine to watch a particular FITS files for
    a modification, indicating a request for a new DM actuation
    state.

    Will ignore the current file if it already exists
    when the monitor starts (until it's modified).
    '''
    def __init__(self, path):
        '''
        Parameters:
            path : str
                Network path to watch for 'dm_input.fits'
                file.
        '''
        super().__init__(os.path.join(path,'dm_input.fits'))

    def on_new_data(self, newdata):
        '''
        On detecting an updated dm_input.fits file,
        load the image onto the DM and write out an
        empty 'dm_ready' file to the network path
        '''
        # Load image from FITS file onto DM channel 0
        log.info('Setting DM from new image file {}'.format(newdata))
        load_channel(newdata, 0)

        # Write out empty file to tell Zygo the DM is ready.
        # Force a new file name with the iterator just to
        # avoid conflicts with past files.
        open(os.path.join(os.path.dirname(self.file), 'dm_ready'), 'w').close()
