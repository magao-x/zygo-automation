'''
Basic idea:
* Following Alex's instruction, set up the DM
to be ready to accept commands and tear it down afterwards
* Use wrapper scripts to generate FITS files and issue commands
to the DM

Initial automation script should just be looping over
each pixel and setting it to some value
    - Will want to eventually generalize to more complicated
    states. How to communicate this to the DM will be tricky.
    - Maybe write out a kernel and a central pixel? Don't know!

'''

import os
import subprocess
import shutil

from astropy.io import fits
import numpy as np

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def load_channel(fits_file, channel):
    script_path = '/home/lab/src/scripts'

    # Copy FITS file over to /home/lab/src/scripts
    shutil.copy2(fits_file, script_path)

    # Call the DM command to load file into channel
    basename = os.path.basename(fits_file)
    subprocess.call(['sh', 'dmloadch', basename, str(channel)],
                     cwd=script_path)

    #Delete afterwards!
    os.remove(os.path.join(script_path, basename))
    
def clear_channel(channel):
    script_path = '/home/lab/src/scripts'
    subprocess.call(['sh', 'dmzeroch', str(channel)],
                     cwd=script_path)

def set_pixel(xpix, ypix, value, xdim=32, ydim=32):
    '''
    Set a single DM actuator to some value.
    '''
    assert isinstance(xpix, int), 'Pixel coordinates must be integers'
    assert isinstance(ypix, int), 'Pixel coordinates must be integers'
    #assert value >= 0 and value <= 1., 'Value must be between 0 and 1! (I think)'

    dm_image = np.zeros((ydim, xdim))
    dm_image[ypix, xpix] = value
    
    return dm_image

def set_row_column(idx, value, dim=0, xdim=32, ydim=32):
    '''
    Set a row or column to some value
    '''
    assert isinstance(idx, int), 'Row/column index must be an integer'
    #assert value >= 0 and value <= 1., 'Value must be between 0 and 1! (I think)'

    dm_image = np.zeros((ydim, xdim))
    if dim == 0:
        dm_image[idx,:] = value
    elif dim == 1:
        dm_image[:,idx] = value
    
    return dm_image

def write_fits(filename, data, overwrite=False):
    '''
    Write data out as a FITS file, as expected
    by Olivier's DM scripts.
    '''
    hdu = fits.PrimaryHDU(data.astype(np.float32))
    hdu.writeto(filename, overwrite=overwrite)