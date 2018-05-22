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

def get_klip_basis(R, cutoff):
    '''
    Succinct KLIP implementation courtesy of N. Zimmerman
    '''
    w, V = np.linalg.eig(np.dot(R, np.transpose(R)))
    sort_ind = np.argsort(w)[::-1] #indices of eigenvals sorted in descending order
    sv = np.sqrt(w[sort_ind]).reshape(-1,1) #column of ranked singular values
    Z = np.dot(1./sv*np.transpose(V[:, sort_ind]), R)
    return Z[0:cutoff, :], sv

def klip_projection(target,reflib,truncation=10):
    refflat = reflib.reshape(reflib.shape[0],-1)
    targflat = target.flatten()
    Z, _ = get_klip_basis(refflat,truncation)
    proj = targflat.dot(Z.T)
    return Z.T.dot(proj).reshape(target.shape)

def get_influence_pseudo_inverse(influence_cube):
    '''
    Given Z x Y x X cube, return the Z x (X * Y)
    flatten IF cube and its pseudo-inverse
    '''
    shape = influence_cube.shape
    F = np.asarray(influence_cube).reshape(shape[0], -1).T
    Finv = np.linalg.pinv(F)
    return F, Finv

def get_strokemap(surface, Finv):
    return np.dot(Finv,surface.flatten())

def predict_stroke(strokemap, F):
    return np.dot(strokemap,F.T)