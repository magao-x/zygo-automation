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

    This assumes you already have the ALPAO control
    loop running and waiting for share memory images
    at <serial>.

    Parameters:
        data : nd array
            97 x 1 nd array of type float64
        serial : str
            DM serial number. Example: "BAX150"
    Returns:
        nothing
    '''

    # check that max/min aren't violated
    if np.any(np.abs(data) > 1):
        raise ValueError("DM97 inputs must be between -1 and +1.")

    #add empty dimension to 1D arrays
    if np.ndim(data) == 1:
        data = np.expand_dims(data,1)
    #connect to shared memory image
    img = shmio.Image()
    img.link(serial)
    #write to shared memory
    img.write(data.astype(np.float64))

def set_single_actuator(n, value):
    '''
    Generate the input array for a single poked
    actuator.

    Parameters:
        n : int
            Actuator number. See actuator_locations_array
        value : float
            Fractional value to place on the DM. Must be
            between -1 and +1.
    Returns:
        inputs : nd array
            97 x 1 array of zeros except for poked actuator
    '''
    if not np.abs(value) <= 1: raise ValueError("DM97 inputs must be between -1 and +1.")
    inputs = np.zeros((97,), dtype=np.float64)
    inputs[n] = value
    return inputs

def set_row_column(idx, value, dim):
    '''
    Generate the input array for a column of poked
    actuators.

    Parameters:
        idx : int
            Column number. See actuator_locations_array
        value : float
            Fractional value to place on the DM. Must be
            between -1 and +1.
        dim : int
            0 or 1. X or Y axis.
    Returns:
        inputs : nd array
            97 x 1 array of zeros except for poked column.
    '''
    array = np.zeros((11,11))
    if dim == 0:
        array[idx,:] = value
    elif dim == 1:
        array[:,idx] = value
    return map_square_to_vector(array)

def influence_function_loop(value):
    '''
    Generate the list of inputs to be looped
    over for influence function characterization.

    Parameters:y
        value : float
            Fractional value to poke each actuator.
            Must be between -1 and +1.
    Returns:
        inputs : list
            list of 97 inputs, one actuator poked in each.
    '''
            
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

    Parameters:
        vector : array-like
            97 element DM input to be embedded
            in 11x11 square array.
    Returns:
        array : nd array
            11x11 square array
    '''
    array = np.zeros((11,11))
    circmask = draw.circle(5,5,5.5,(11,11))
    array[circmask] = vector
    return array

def map_square_to_vector(array):
    '''
    Given the dm data values embedded
    in a square (11x11) array, pull out
    the actuator values in an properly ordered
    vector (that could be passed directly to the 
    ALPAO SDK)

    Parameters:
        array : nd array
            2D (11x11) array of DM inputs
    Returns:
        vector : nd array
            97-element input vector
    '''
    circmask = draw.circle(5,5,5.5,(11,11))
    return array[circmask]

def actuator_locations_array():
    '''
    Generate an 11x11 array showing
    the DM locations and numbering scheme.

    If plotted in matplotlib (origin='upper'),
    this is consistent with the DM as seen
    from the Zygo.
    '''
    square = np.zeros((11,11))
    circmask = draw.circle(5,5,5.5,(11,11))
    square[circmask] = np.arange(1,98)
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