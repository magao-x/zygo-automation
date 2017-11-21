import os
import subprocess
import shutil

from astropy.io import fits
import numpy as np

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def load_channel(fits_file, channel):
    '''
    Load a fits file into a channel on the BMC DM.

    This is hard-coded to the paths on Corona.

    Parameters:
        fits_file : str
            Path to FITS file to load
        channel : int
            Integer channel to load FITS file onto
    Returns: nothing
    '''
    script_path = '/home/lab/src/scripts'
    basename = os.path.basename(fits_file)


    # Copy FITS file over to /home/lab/src/scripts
    if not os.path.exists(os.path.join(scrip_path, basename)):
        shutil.copy2(fits_file, script_path)
    else:
        raise Exception('The file {} already exists in {}.'.format(basename, script_path))

    # Call the DM command to load file into channel
    subprocess.call(['sh', 'dmloadch', basename, str(channel)],
                     cwd=script_path)

    #Delete afterwards!
    os.remove(os.path.join(script_path, basename))
    
def clear_channel(channel):
    '''
    Clear channel with the dmzeroch command.
    '''
    script_path = '/home/lab/src/scripts'
    subprocess.call(['sh', 'dmzeroch', str(channel)],
                     cwd=script_path)

def set_pixel(xpix, ypix, value, xdim=32, ydim=32):
    '''
    Set a single DM actuator to some value.

    Parameters:
        xpix, ypix : int
            X, Y pixels of the pixel to set.
        value : float
            Value to set the pixel to
        xdim, ydim: int
            X, Y dimensions of the DM actuators.
    Returns:
        dm_image : nd array
            ydim x xdim array of values
    '''
    dm_image = np.zeros((ydim, xdim))
    dm_image[ypix, xpix] = value
    
    return dm_image

def set_row_column(idx, value, dim=0, xdim=32, ydim=32):
    '''
    Set a row or column on the DM to some value.

    Parameters:
        idx : int
            Index of the row or column to set
        value : float
            Value to set the row/column to
        dim : int
            0 or 1. Set row or column.
        xdim, ydim: int
            X, Y dimensions of the DM.
    Returns:
        dm_image : nd array
            ydim x xdim array of values
    '''

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

    Parameters:
        filename : str
            Filename to write out.
        data : nd array
            Data to write in the FITS file.
            This will be cast to a float32.
        overwrite : bool, opt
            Overwrite the file if it already
            exists?
    Returns: nothing
    '''
    hdu = fits.PrimaryHDU(data.astype(np.float32))
    hdu.writeto(filename, overwrite=overwrite)