import os, sys

import numpy as np
import h5py

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Add zygo script directory to sys path
try:
    # Hard-coded path to Python scripting library on Zygo machine
    sys.path.append('C:\ProgramData\Zygo\Mx\Scripting')
    import zygo
    from zygo import mx, instrument, systemcommands, connectionmanager, ui
    from zygo.units import Units
    # connect to Mx session (Mx must be open!)
    connectionmanager.connect()
except ImportError:
    log.warning('Could not load Zygo Python library! Functionality will be severely crippled.')

def capture_frame(filename=None):
    '''
    Capture an image on the Zygo via Mx.

    Parameters:
        filename : str (optional)
            Filename of output. If not provided, Mx will
            capture the image and load it into the interface
            but it's up to the user to use the GUI to save
            it out.

    The output is a .datx file that includes the raw surface 
    (no Zernike modes removed, even if selected in Mx), intensity,
    and Mx attributes.

    It's expected that all capture parameters will be set manually
    in Mx: exposure time, masks, etc. I think this makes the most
    sense, since these things have to be determined interactively
    anyway.
    '''
    log.info('Mx: capturing fram and acquiring from camera.')
    instrument.measure()
    instrument.acquire()

    if filename is not None:
        log.info('Mx: writing out to {}'.format(filename))
        mx.save_data(filename)

def save_surface(filename):
    '''
    Save the surface currently loaded in Mx out
    as a .datx. This may or may not remove Zernikes.
    I need to figure that out.

    Parameters:
        filename : str
            Filename to save surface out to (as a .datx)

    This mostly serves as an example of how to grab data
    from Mx control elements. control_path can be found
    by right-clicking on a GUI element in Mx in choosing
    the "control path"(?) option in the dropdown.

    '''
    control_path = ("MEASURE", "Measurement", "Surface", "Surface Data")
    surface_control = ui.get_control(control_path)
    surface_control.save_data(filename) # .datx?

def read_hdf5(filename, mode='r'):
    '''
    Simple wrapper around h5py to load a file
    up (just because I have a hard time remembering
    the syntax).

    Parameters:
        filename : str
            File to open
        mode : str (optional)
            Mode to open file in.
    Return : nothing
    '''
    return h5py.File(filename, mode)

def open_in_Mx(filename):
    '''
    Open a .datx file in Mx

    Parameters:
        filename : str
            File path to open.
    Returns: nothing
    '''
    mx.load_data(filename)

def parse_raw_datx(filename, attrs_to_dict=True, mask_and_scale=False):
    '''
    Given a .datx file containing raw surface measurements,
    return a dictionary of the surface and intensity data,
    as well as file and data attributes.
    
    Parameters:
        filename : str
            File to open and raw (.datx)
        attrs_to_dict : bool, opt
            Cast h5py attributes objects to dicts
        mask_and_scale : bool, opt
            Mask out portion of surface/intensity
            maps with no data and scale from wavefront
            wavelengths to surface microns.

    Returns: dict of surface, intensity, masks, and attributes

    I really dislike this function, but the .datx files are a mess
    to handle in h5py without a wrapper like this. 
    '''
    
    h5file = h5py.File(filename, 'r')
    
    assert 'Measurement' in list(h5file.keys()), 'No "Measurement" key found. Is this a raw .datx file?' 
    
    # Get surface and attributes
    surface = h5file['Measurement']['Surface'].value
    surface_attrs = h5file['Measurement']['Surface'].attrs
    # Define the mask from the "no data" key
    mask = np.ones_like(surface).astype(bool)
    mask[surface == surface_attrs['No Data']] = 0
    # Mask the surface and scale to surface in microns if requested
    if mask_and_scale:
        surface[~mask] = 0
        surface *= surface_attrs['Interferometric Scale Factor'][0] * surface_attrs['Wavelength'] * 1e6
    
    # Get file attributes (overlaps with surface attrs, I believe)

    attrs = h5file['Measurement']['Attributes'].attrs
    
    # Get intensity map
    intensity = h5file['Measurement']['Intensity'].value
    intensity_attrs = h5file['Measurement']['Intensity'].attrs

    if attrs_to_dict:
        surface_attrs = dict(surface_attrs)
        attrs = dict(attrs)
        intensity_attrs = dict(intensity_attrs)
    
    return {
        'surface' : surface,
        'surface_attrs' : surface_attrs,
        'mask' : mask,
        'intensity' : intensity,
        'intensity_attrs' : intensity_attrs,
        'attrs' : attrs 
    }

def read_many_raw_datx(filenames, attrs_to_dict=True, mask_and_scale=False):
    '''
    Simple loop over many .datx files and consolidate into a list
    of surfaces, intensity maps, and attributes 

    Parameters:
        filenames: list
            List of strings pointing to filenames
        attrs_to_dict : bool, opt
            Cast h5py attributes objects to dicts
        mask_and_scale : bool, opt
            Mask out portion of surface/intensity
            maps with no data and scale from wavefront
            wavelengths to surface microns. 

    Returns: list of dicts. See parse_raw_datx.
    '''
    consolidated = {
        'surface' : [],
        'surface_attrs' : [],
        'intensity' : [],
        'intensity_attrs' : [],
        'attrs' : [],
        'mask' : [],
    }
    for f in filenames:
        fdict = parse_raw_datx(f, attrs_to_dict=attrs_to_dict, mask_and_scale=mask_and_scale)
        for k in fdict.keys():
            consolidated[k].append(fdict[k])
    return consolidated

def parse_processed_datx(filename):
    '''
    Parse .datx file with processed data

    A separate function is necessary since Mx
    structures the processed .datx files differently.
    '''
    pass
    
def process_and_export_in_Mx(filename):
    '''
    Open a raw .datx file in Mx and save out the processed
    surface.

    This function is intended to be useful to reading in
    a set of raw measurements (.datx files taken previously),
    performing some processing in Mx (zernike-removal, for example),
    and writing out the processed surfaces.
    '''
    pass