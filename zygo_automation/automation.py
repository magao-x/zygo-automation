from itertools import product
import glob as glob
import os
import tempfile
from time import sleep

import h5py
import numpy as np

from .capture import capture_frame, read_many_raw_datx
from .dm import load_channel, set_pixel, set_row_column, write_fits

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


'''
Expected use:
* Start DM Monitor on Corona
* Get Zygo mask, exposure, etc. set up in Mx
* Call Zygo-DM function to loop through 
desired DM inputs and take Zygo images
'''

def Zygo_DM_Run(dm_inputs, network_path, outname, dry_run=False):
    '''
    DMMonitor must be active before
    executing?

    Parameters:
        dm_inputs: list
            List of images?
    Returns:

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
            capture_frame(filename=os.path.join(outname,'frame_{}.datx'.format(idx)))

        # Remove input file
        if os.path.exists(input_file):
            os.remove(input_file)

    log.info('Writing to consolidated .hdf5 file.')
    # Consolidate individual frames and inputs
    alldata = read_many_raw_datx(glob.glob(os.path.join(outname,'frame_*.datx')), mask_and_scale=False)
    write_dm_run_to_hdf5(os.path.join(outname,'alldata.hdf5'),
                         np.asarray(alldata['surface']),
                         alldata['surface_attrs'][0],
                         np.asarray(alldata['intensity']),
                         alldata['intensity_attrs'][0],
                         alldata['attrs'][0],
                         np.asarray(dm_inputs),
                         alldata['mask'][0]
                         )

def write_dm_run_to_hdf5(filename, surface_cube, surface_attrs, intensity_cube, intensity_attrs, all_attributes, dm_inputs, mask):
    # create hdf5 file
    f = h5py.File(filename)
    
    # surface data and attributes
    surf = f.create_dataset('surface', data=surface_cube)
    for k, v in surface_attrs.items(): # attrs.update method crashes python
        surf.attrs[k] = v

    intensity = f.create_dataset('intensity', data=intensity_cube)
    for k, v in intensity_attrs.items():
        intensity.attrs[k] = v

    attributes = f.create_group('attributes')
    for k, v in all_attributes.items():
        attributes.attrs[k] = v

    dm_inputs = f.create_dataset('dm_inputs', data=dm_inputs)
    dm_inputs.attrs['units'] = 'microns'

    mask = f.create_dataset('mask', data=mask)
    
    f.close()

def test_inputs_pixel(xpix, ypix, val):
    pixel_list = product(range(xpix), range(ypix), [val,] )
    image_list = []
    for pix in pixel_list:
        image_list.append( set_pixel(*pix) )
    return image_list

def test_inputs_row_column(num_cols, val, dim=0):
    image_list = []
    for col in range(num_cols):
        image_list.append( set_row_column(col, val, dim=dim) )
    return image_list

class FileMonitor(object):
    '''
    Watch a file for modifications at some
    cadence and perform some action when
    it's modified.  
    '''
    def __init__(self, file_to_watch):
        self.file = file_to_watch
        self.continue_monitoring = True

        # Find initial state
        self.last_modified = self.get_last_modified(self.file)

    def watch(self, period=1.):
        '''
        Pick out new data that have appeared since last query
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
        pass

class ZygoMonitor(FileMonitor):
    '''
    Set the Zygo machine to watch for an indication from
    the DM that it's been put in the requested state,
    and proceed with data collection when ready
    '''
    def __init__(self, path):
        super().__init__(os.path.join(path,'dm_ready'))

    def on_new_data(self, newdata):
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
        super().__init__(os.path.join(path,'dm_input.fits'))

    def on_new_data(self, newdata):
        # Load image from FITS file onto DM channel 0
        log.info('Setting DM from new image file {}'.format(newdata))
        load_channel(newdata, 0)

        # Write out empty file to tell Zygo the DM is ready.
        # Force a new file name with the iterator just to
        # avoid conflicts with past files.
        open(os.path.join(os.path.dirname(self.file), 'dm_ready'), 'w').close()
