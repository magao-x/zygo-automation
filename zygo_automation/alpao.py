'''
Functions for commanding ALPAO DM97 via
shared memory images, as implemented in milk.

'''

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

try:
    import pyImageStreamIO as shmio #shared memory io
except ImportError:
    log.warning('Could not load pyImageStreamIO package! You will not be able to command the ALPAO.')

import numpy as np
from skimage import draw
import poppy

def apply_command(data, serial):
    '''
    Apply a command to an ALPAO DM via shared
    memory image.

    Parameters:
        data : nd array
            97 x 1 nd array of type float64
        serial : str
            DM serial number. Example: "BAX150"
    Returns:
        nothing
    '''

    #add empty dimension to 1D arrays
    if np.ndim(data) == 1:
        data = np.expand_dims(data,1)
    #connect to shared memory image
    img = shmio.Image()
    img.link(serial)
    #write to shared memory
    img.write(data)

def release_mirror(serial):
    log.warning("This doesn't do anything yet! The DM is NOT released.")
    pass

def set_single_actuator(n, value):
    if not np.abs(value) <= 1: raise ValueError("DM97 inputs must be between -1 and +1.")
    inputs = np.zeros((97,), dtype=np.float64)
    inputs[n] = value
    return inputs

def set_row_column(idx, value, dim):
    array = np.zeros((11,11))
    if dim == 0:
        array[idx,:] = value
    elif dim == 1:
        array[:,idx] = value
    return map_square_to_vector(array)

def influence_function_loop(value):
    allinputs = []
    for n in range(97):
        allinputs.append(set_single_actuator(n, value))
    return allinputs

def map_vector_to_square(vector):
    '''
    Given the DM data values in a vector
    ordered by actuator number, embed the
    data in a square array (primarily for 
    visualization purposes).
    '''
    array = np.zeros((11,11))
    circmask = draw.circle(5,5,5.5,(11,11))
    array[circmask] = vector
    array = array[:,::-1].T
    return array

def map_square_to_vector(array):
    '''
    Given the dm data values embedded
    in a square (11x11) array, pull out
    the actuator values in an properly ordered
    vector (that could be passed directly to the 
    ALPAO SDK)
    '''
    circmask = draw.circle(5,5,5.5,(11,11))
    return array[::-1,:].T[circmask]

def actuator_locations_array():
    #Actuator locations defined on 11x11 array
    square = np.zeros((11,11))
    circmask = draw.circle(5,5,5.5,(11,11))
    square[circmask] = np.arange(1,98)
    square = square[:,::-1].T
    return square

def generate_zernike_modes(nterms=15,to_vector=True):
    '''
    Generate Zernike modes orthonormalized on actuator
    array.

    Parameters:
        nterms: int
            Number of zernike modes
        to_vector:
            Return modes as vectors in 
            actuator order
    Returns:
        zbasis: array of 1D or 2D arrays of zernike modes
    '''
    aperture = np.zeros((11,11))
    circmask = draw.circle(5,5,5.5,(11,11))
    aperture[circmask] = 1

    zbasis = poppy.zernike.arbitrary_basis(aperture,nterms=nterms,outside=0)

    if to_vector:
        return [map_square_to_vector(z) for z in zbasis]
    else:
        return zbasis