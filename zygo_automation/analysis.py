import numpy as np
import poppy

from scipy.optimize import leastsq

def rms(image,mask=None):
    return np.sqrt(np.mean(image[mask]**2))

def plane(indices, piston, tip, tilt):
    return piston + indices[1]*tip + indices[0]*tilt

def plane_error(params, indices, image, mask):
    delta = plane(indices,*params) - image
    return delta[mask].flatten()

def fit_plane(image, mask=None, indices=None):
    if indices is None:
        indices = np.indices(image.shape)
    return leastsq(plane_error, [0.,0.,0.], args=(indices, image, mask))[0]

def fit_ptt(image, aperture):
    basis = poppy.zernike.arbitrary_basis(aperture, nterms=3)
    def return_basis(*args, **kwargs):
        return basis
    return poppy.zernike.opd_expand(image, aperture=aperture, nterms=3, basis=return_basis)

def surface_from_ptt(coeffs, aperture):
    basis = poppy.zernike.arbitrary_basis(aperture, nterms=3)
    def return_basis(*args, **kwargs):
        return basis
    return poppy.zernike.opd_from_zernikes(coeffs, basis=return_basis)

def squarify(a, pad_value=0):
    shape = a.shape
    to_add = max(shape) - min(shape)
    if shape[0] <= shape[1]:
        padding = ((to_add//2, to_add//2),(0,0))
    else:# shape[1] > shape[0]:
        padding = ((0,0),(to_add//2, to_add//2))
    return np.pad(a, padding, mode='constant', constant_values=0. )