'''
Tools for interfacing with Basler cameras

example usage:

# Find and open a camera
>>> available_cameras = find_devices()
>>> cam = create_device(available_cameras[0])
>>> cam.open()

# Set camera properties
>>> cam.properties['ExposureTime'] = 500.
>>> cam.properties['DeviceLinkThroughputLimitMode'] = 'Off'

# Grab a single image
>>> image = cam.grab_image()

# Grab multiple images
>>> imagelist = cam.grab_images(10)
'''

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

try:
	import pypylon as pp
except ImportError:
	    log.warning('Could not load pypylon package! Basler functionality will be severely crippled.')
	    
def find_devices():
	return pp.factory.find_devices()

def create_device(device):
	return pp.factor.create_device(device)