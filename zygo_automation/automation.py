import glob as glob
import os
from time import sleep

import h5py
import numpy as np
from astropy.io import fits

from .zygo import capture_frame, read_many_raw_datx
from .bmc import load_channel, write_fits, update_voltage_2K
from .irisao import write_ptt_command, apply_ptt_command
from . import alpao

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def zygo_dm_run(dm_inputs, network_path, outname, dmtype, delay=None, consolidate=True, dry_run=False, clobber=False, mtype='acquire', input_name='dm_inputs.fits'):
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
        dmtype : str
            'bmc', 'irisao', or 'alpao'. This determines whether
            the dm_inputs are written to .fits or .txt.
        outname : str
            Directory to write results out to. Directory
            must not already exist.
        delay : float, opt.
            Time in seconds to wait between measurements.
            Default: no delay.
        consolidate : bool, opt.
            Attempt to consolidate all files at the end?
            Default: True
        dry_run : bool, opt.
            If toggled to True, this will loop over DM states
            without taking images. This is useful to debugging
            things on the DM side / watching the fringes on
            the Zygo live monitor.
        clobber : bool, opt.
            Allow writing to directory that already exists?
            Risks overwriting files that already exist, but
            useful for interactive measurements.
        mtype : str
            'acquire' or 'measure'. 'Acquire' takes a measurement
            without analyzing or updating the GUI (faster), while
            'measure' takes a measurement, analyzes, and updates
            the GUI (slower).
    Returns: nothing

    '''
    if dmtype.upper() not in ['BMC','IRISAO','ALPAO']:
        raise ValueError('dmtype not recognized. Must be either "BMC" or "IRISAO".')

    if not (dry_run or clobber):
        # Create a new directory outname to save results to
        assert not os.path.exists(outname), '{} already exists!'.format(outname)
        os.mkdir(outname)

    zm = ZygoMonitor(network_path)

    for idx, inputs in enumerate(dm_inputs):

        if (dmtype.upper() == 'BMC') or (dmtype.upper() == 'ALPAO'):
            #Remove any old inputs if they exist
            old_files = glob.glob(os.path.join(network_path,'dm_input*.fits'))
            for old_file in old_files:
                if os.path.exists(old_file):
                    os.remove(old_file)
            # Write out FITS file with requested DM input
            log.info('Setting DM to state {}/{}.'.format(idx + 1, len(dm_inputs)))
            input_file = os.path.join(network_path,input_name)
            # write out
            if dmtype.upper() == 'ALPAO':
                alpao.command_to_fits(inputs, input_file, overwrite=True)
            else: #BMC
                write_fits(input_file, inputs, dtype=np.float32, overwrite=True)
        else: #IRISAO
            input_file = os.path.join(network_path,'ptt_input.txt'.format(idx))
            write_ptt_command(inputs, input_file)

        # Wait until DM indicates it's in the requested state
        # I'm a little worried the DM could get there before
        # the monitor starts watching the dm_ready file, but 
        # that hasn't happened yet.
        zm.watch(0.01)
        log.info('DM ready!')

        if not dry_run:
            # Take an image on the Zygo
            log.info('Taking image!')
            capture_frame(filename=os.path.join(outname,'frame_{0:05d}.datx'.format(idx)),
                          mtype=mtype)

        # Remove input file
        if os.path.exists(input_file):
            os.remove(input_file)

        if delay is not None:
            sleep(delay)

    if consolidate:
        log.info('Writing to consolidated .hdf5 file.')
        # Consolidate individual frames and inputs
        # Don't read attributes into a dictionary. This causes python to crash (on Windows)
        # when re-assignging them to hdf5 attributes.
        alldata = read_many_raw_datx(sorted(glob.glob(os.path.join(outname,'frame_*.datx'))), 
                                     attrs_to_dict=True, mask_and_scale=True)
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
    f = h5py.File(filename, 'w')
    
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
        self.continue_monitoring = True
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

class BMC1KMonitor(FileMonitor):
    '''
    Set the DM machine to watch a particular FITS files for
    a modification, indicating a request for a new DM actuation
    state.

    Will ignore the current file if it already exists
    when the monitor starts (until it's modified).
    '''
    def __init__(self, path, input_file='dm_input.fits'):
        '''
        Parameters:
            path : str
                Network path to watch for 'dm_input.fits'
                file.
        '''
        super().__init__(os.path.join(path, input_file))

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
        open(os.path.join(os.path.dirname(self.file), 'dm_ready'), 'w').close()

class BMC2KMonitor(FileMonitor):
    '''
    Set the DM machine to watch a particular FITS files for
    a modification, indicating a request for a new DM actuation
    state.

    Will ignore the current file if it already exists
    when the monitor starts (until it's modified).
    '''
    def __init__(self, path, serial, input_file='dm_input.fits', script_path='/home/kvangorkom/BMC-interface'):
        '''
        Parameters:
            path : str
                Network path to watch for 'dm_input.fits'
                file.
        '''
        super().__init__(os.path.join(path, input_file))
        self.serial = serial
        self.script_path = script_path

    def on_new_data(self, newdata):
        '''
        On detecting an updated dm_input.fits file,
        load the image onto the DM and write out an
        empty 'dm_ready' file to the network path
        '''
        # Load image from FITS file onto DM channel 0
        log.info('Setting DM from new image file {}'.format(newdata))
        update_voltage_2K(newdata, self.serial, self.script_path)

        # Write out empty file to tell Zygo the DM is ready.
        open(os.path.join(os.path.dirname(self.file), 'dm_ready'), 'w').close()

class ALPAOMonitor(FileMonitor):
    '''
    Set the DM machine to watch a particular FITS files for
    a modification, indicating a request for a new DM actuation
    state.

    Will ignore the current file if it already exists
    when the monitor starts (until it's modified).
    '''
    def __init__(self, path, serial, input_file='dm_input.fits'):
        '''
        Parameters:
            path : str
                Network path to watch for 'dm_input.fits'
                file.
            serial : str
                ALPAO DM97 serial number. Probably "BAX150"
        '''
        super().__init__(os.path.join(path, input_file))
        self.serial = serial
        #self.img = alpao.link_to_shmimage(serial)

    def on_new_data(self, newdata):
        '''
        On detecting an updated dm_input.fits file,
        load the image onto the DM and write out an
        empty 'dm_ready' file to the network path
        '''
        # Load image from FITS file onto DM channel 0
        log.info('Setting DM from new image file {}'.format(newdata))
        #alpao.apply_command(fits.open(newdata)[0].data, self.serial, self.img)
        alpao.apply_command_from_fits(newdata, self.serial)

        # Write out empty file to tell Zygo the DM is ready.
        open(os.path.join(os.path.dirname(self.file), 'dm_ready'), 'w').close()

class IrisAOMonitor(FileMonitor):
    '''
    Set the DM machine to watch a particular FITS files for
    a modification, indicating a request for a new DM actuation
    state.

    Will ignore the current file if it already exists
    when the monitor starts (until it's modified).
    '''
    def __init__(self, path, mserial, input_file='ptt_input.txt'):
        '''
        Parameters:
            path : str
                Network path to watch for 'ptt_input.txt'
                file.
        '''
        super().__init__(os.path.join(path, input_file))
        self.mserial = mserial

    def on_new_data(self, newdata):
        '''
        On detecting an updated dm_input.fits file,
        load the image onto the DM and write out an
        empty 'dm_ready' file to the network path
        '''
        # Load image from FITS file onto DM channel 0
        log.info('Setting DM from new PTT file {}'.format(newdata))
        apply_ptt_command(newdata, mserial=self.mserial)

        # Write out empty file to tell Zygo the DM is ready.
        open(os.path.join(os.path.dirname(self.file), 'dm_ready'), 'w').close()

class BaslerMonitor(FileMonitor):
    def __init__(self, path, camera, images, stop_after_capture=False, nimages=1):
        '''
        Parameters:
            path : str
                Network path to watch for 'dm_ready'
                file indicating the DM is in the
                requested state.
            camera : pypylon camera object
            images : list
                List to append images to
            stop_after_capture : bool, opt.
                Stop monitor after capturing an 
                image? Default: False.
            nimages : int, opt.
                Take multiple images? If > 1, each element
                of the image list will be an array of images
        '''
        super().__init__(os.path.join(path,'dm_ready'))
        
        self.camera = camera
        self.images = images
        self.stop_after_capture = stop_after_capture
        self.nimages = nimages

    def on_new_data(self, newdata):
        '''
        On detecting a new 'dm_ready' file, capture
        an image on the Basler camera.
        '''
        if self.nimages == 1:
            self.images.append(self.camera.grab_image().astype(float))
        else:
            self.images.append(np.asarray(list(self.camera.grab_images(self.nimages))).astype(float))
        log.info('Grabbed Basler frame! ({})'.format(len(self.images)))
        open(os.path.join(os.path.dirname(self.file), 'basler_ready'), 'w').close()
        if self.stop_after_capture:
            self.continue_monitoring = False
