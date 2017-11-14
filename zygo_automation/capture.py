import os, sys

import numpy as np
import h5py

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Add zygo script directory to sys path
try:
    sys.path.append('C:\ProgramData\Zygo\Mx\Scripting') # this is hard-coded...
    import zygo
    from zygo import mx, instrument, systemcommands, connectionmanager, ui
    from zygo.units import Units
    # connect to Mx session (Mx must be open!)
    connectionmanager.connect()
except ImportError:
    log.warning('Could not load Zygo Python library! Functionality will be severely crippled.')


def capture_frame(exposure_time=None, filename=None):
    '''
    Capture an image and return the unwrapped surface.

    Right now, this is removing piston and tip/tilt. Should be
    settable either in the UI by adjusting "Surface Processing"
    or via the API by finding the control for that window.

    This'll need to be expanded to allow manually setting camera parameters
    as well as choosing how Mx should process the surface (what terms to remove, etc)

    Because the Python API doesn't appear to allow acquiring the image data
    directly from Mx, this currently saves out the files to a .SDF file and then
    reads them back in. (Actually: can save out .datx and parse those because
    they're just HDF5.)


    Right now, assumes you're setting the mask manually in Mx.
    '''
    log.info('(X, Y): ({}, {})'.format(instrument.get_cam_size_x(Units.Pixels), instrument.get_cam_size_y(Units.Pixels)))

    log.info('Capturing frame.')
    instrument.measure()

    log.info('Acquiring from camera.')
    instrument.acquire()

    if filename is not None:
        mx.save_data(filename)
        #save_frame(filename)
        #return read_frame(filename)

def capture_many_frames(nframes, filename_format):
    '''
    filename_format: /path/to/files_{}.sdf
    '''
    headers = []
    frames = []
    for n in range(nframes):
        outname = filename_format.format(n)
        header, frame = capture_frame(filename=outname)
        headers.append(header)
        frames.append(frame)
    return headers, frames

def save_frame(filename):
    '''
    For now, I'm assuming we'll save these out to SDF

    Raw data: ("MEASURE", "Raw Data", "Raw Data", "Raw Data")
    '''
    control_path = ("MEASURE", "Measurement", "Surface", "Surface Data")
    surface_control = ui.get_control(control_path)
    #params = surface_control.SdfParams()
    surface_control.save_data(filename+'.datx') #optional_params=params

def read_frame(filename):
    '''
    Parse an SDF file and return the header and data.
    '''
    with open(filename) as f:

        headerlist = [f.readline() for x in range(13)] # assume fixed header line length
        header = parse_header(headerlist[1:])
        f.readline() #throw away

        data = f.read().split('\n')
        data = np.asarray(data[:-2], dtype=float).reshape(1024,1024)
        data[data == 1.79e+308] = 0
    return header, data

def parse_header(header):
    header_dict = {}
    for line in header:
        split = line.split('=')
        key = split[0].rstrip()
        val = split[-1].rstrip()
        header_dict[key] = val
    return header_dict

def read_hdf5(filename, mode='r'):
    '''
    Open a Zygo .datx file via h5py
    
    '''

    return h5py.File(filename, mode)

def open_in_Mx(filename):
    '''
    Open a .datx file in Mx

    Will probably want to pair this with
    a few wrappers around basic processing
    in Mx (removing Zernike terms from surface,
    getting PSD, etc.)

    To grab the data after processing, however,
    you might still need to write out to SDF?
    Unless Mx saves the processing in the HDF5
    file, but I don't think it does unless
    you request that processed data be saved
    (in a separate file)
    '''
    mx.load_data(filename)

def parse_raw_datx(filename, mask_and_scale=False):
    '''
    Given a .datx file containing raw surface measurements,
    return a dictionary of the surface and intensity data,
    as well as file and data attributes.   
    
    mask_and_scale : mask out no-data values, scale to surface, and
    convert to microns
    '''
    
    h5file = h5py.File(filename)
    
    assert 'Measurement' in list(h5file.keys()), 'No "Measurement" key found. Is this a raw .datx file?' 
    
    # Get surface and attributes
    surface = h5file['Measurement']['Surface'].value
    surface_attrs = dict(h5file['Measurement']['Surface'].attrs)
    # Define the mask from the "no data" key
    mask = np.ones_like(surface).astype(bool)
    mask[surface == surface_attrs['No Data']] = 0
    # Mask the surface and scale to surface in microns if requested
    if mask_and_scale:
        surface[~mask] = 0
        surface *= surface_attrs['Interferometric Scale Factor'][0] * surface_attrs['Wavelength'] * 1e6
    
    # Get file attributes (overlaps with surface attrs, I believe)
    attrs = dict(h5file['Measurement']['Attributes'].attrs)
    
    # Get intensity map
    intensity = h5file['Measurement']['Intensity'].value
    intensity_attrs = dict(h5file['Measurement']['Intensity'].attrs)
    
    return {
        'surface' : surface,
        'surface_attrs' : surface_attrs,
        'mask' : mask,
        'intensity' : intensity,
        'intensity_attrs' : intensity_attrs,
        'attrs' : attrs 
    }

def read_many_raw_datx(filenames, mask_and_scale=False):
    '''
    Simple loop over many .datx files and consolidate into a list
    of surfaces, intensity maps, and attributes 
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
        fdict = parse_raw_datx(f, mask_and_scale=mask_and_scale)
        for k in fdict.keys():
            consolidated[k].append(fdict[k])
    return consolidated

def parse_processed_datx(filename):
    '''
    Parse .datx file with processed data  
    '''
    pass
    
def process_and_export_in_Mx(filename):
    '''
    Open a raw .datx file in Mx and save out the processed
    surface.
    '''
    pass