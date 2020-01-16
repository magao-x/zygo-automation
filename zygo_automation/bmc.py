import os
from itertools import product
import subprocess
import shutil

from astropy.io import fits
import numpy as np
from skimage import draw

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


# vestige of old API. Leaving for now.
#def update_dmvolt_2K(filename):
#    '''
#
#    Loads a fits file onto the dmvolt shared memory
#    image on the 2K.
#
#    Parameters:
#        filename : str
#            Path to FITS file with 50x50 array of type uint16
#    Returns:
#        nothing
#    '''
#    script_path = '/home/kvangorkom/dmcontrol'
#    subprocess.call(['sh', 'dm_update_volt', filename], cwd=script_path)

def update_voltage_2K(filename, serial, script_path='/home/kvangorkom/BMC-interface'):
    '''
    Interface with the modern BMC API. Load a voltage map
    onto the 2K.

    Parameters:
        filename : str
            Path to FITS file with 2040x1 array of type float32
    Returns:
        nothing
    '''
    subprocess.call(['sh', 'loadfits', filename, serial], cwd=script_path)

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
    if not os.path.exists(os.path.join(script_path, basename)):
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

def dm_shutoff():
    '''
    Shut off the DM with the dmoff command.
    '''
    script_path = '/home/lab/src/scripts'
    subprocess.call(['sh', 'dmoff'], cwd=script_path)

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

def influence_cube_2K(val):
    return [set_pixel(0, i, val, xdim=1, ydim=2040) for i in range(2040)]

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
        image_list.append( set_pixel(xdim=xpix, ydim=ypix, *pix) )
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
        im1 = set_row_column(0, 1, dim=0, xdim=xdim, ydim=ydim)
        im2 = set_row_column(-1, 1, dim=0, xdim=xdim, ydim=ydim)
        im3 = set_row_column(0, 1, dim=1, xdim=xdim, ydim=ydim)
        im4 = set_row_column(-1, 1, dim=1, xdim=xdim, ydim=ydim)
        image = (im1 + im2 + im3 + im4).astype(bool)
        image_list.append(image.astype(int) * val)

    return image_list

def write_fits(filename, data, dtype=np.float32, overwrite=False):
    '''
    Write data out as a FITS file, as expected
    by Olivier's DM scripts.

    Parameters:
        filename : str
            Filename to write out.
        data : nd array
            Data to write in the FITS file.
            This will be cast to a float32.
        dtype : np data type
            Displacement commands need to be
            in float32. cacao dmvolt commands need to
            be in uint16.
        overwrite : bool, opt
            Overwrite the file if it already
            exists?
    Returns: nothing
    '''
    hdu = fits.PrimaryHDU(data.astype(dtype))
    hdu.writeto(filename, overwrite=overwrite)
    

def map_vector_to_square_2K(vector):
    '''
    Given the DM data values in a vector
    ordered by actuator number, embed the
    data in a square array.
    Parameters:
        vector : array-like
            2040-element DM input to be embedded
            in 50x50 square array.
    Returns:
        array : nd array
            50x50 square array
    '''
    array = np.zeros((50,50))
    mask = mask_2K()
    array[mask] = vector
    return array

def map_square_to_vector_2K(array):
    '''
    Given the dm data values embedded
    in a square (50x50) array, pull out
    the actuator values in an properly ordered
    vector.
    Parameters:
        array : nd array
            2D (50x50) array of DM inputs
    Returns:
        vector : nd array
            2040-element input vector
    '''
    mask = mask_2K()
    return array[mask]

def actuator_locations_array_2K():
    '''
    Generate an 50x50 array showing
    the DM locations and numbering scheme.
    If plotted in matplotlib (origin='upper'),
    this is consistent with the DM as seen
    from the Zygo.
    '''
    arr = map_vector_to_square(np.arange(1,2041))
    mask = bmc2k_mask()
    arr[~mask] = np.nan
    return arr.T[:,::-1]

def mask_2K():
    mask = np.zeros((50,50), dtype=bool)
    circmask = draw.circle(24.5,24.5,25.6,(50,50))
    mask[circmask] = 1
    return mask