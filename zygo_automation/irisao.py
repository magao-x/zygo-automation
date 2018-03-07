import csv
import subprocess
import numpy as np

from scipy.ndimage import label
from scipy.ndimage.measurements import center_of_mass as com

from . import analysis

def apply_ptt_command(pttfile, mserial='PWA37-05-04-0404', dserial='09150004',
                      script_path='/home/lab/IrisAO/SourceCodes', hardware_disable=False):
    '''
    Apply a PTT command to the IrisAO from a .txt file.

    Parameters:
        pttfile : str
            Path to .txt file. Expected format is a file with nsegment
            lines, each line of which is a space-delimited list of 
            piston, tip, tilt coeffcients. (micron, mrad, mrad)
        mserial : str
            Mirror serial number
        dserial : str
            Driver serial number
        script_path : str
            Path to IrisAO scripts.
        hardware_disable : bool
            Disable the hardware? Toggle to True for dry runs.

    Returns: nothing
    '''
    # run Alex's C code (needs to have root privileges...)
    subprocess.call(['sudo', './SendPTT', mserial, dserial, str(int(hardware_disable)), pttfile],
                     cwd=script_path)

def release_mirror(mserial='PWA37-05-04-0404', dserial='09150004',
                   script_path='/home/lab/IrisAO/SourceCodes', hardware_disable=False):
    # run Alex's C code (needs to have root privileges...)
    subprocess.call(['sudo', './Release', mserial, dserial], cwd=script_path)

def flatten_mirror(mserial='PWA37-05-04-0404', dserial='09150004',
                   script_path='/home/lab/IrisAO/SourceCodes', hardware_disable=False):
    # run Alex's C code (needs to have root privileges...)
    subprocess.call(['sudo', './Flatten2', mserial, dserial], cwd=script_path)

def build_segment_command(n, nsegments=37, piston=0., tip=0., tilt=0., addto=None):
    '''
    Convenience function to allow commanding a single segment
    with some set of PTT values.

    Parameters:
        n : int
            Which segment to command?
        nsegments : int
            Total number of segments in the IrisAO DM
        piston : float
            Value in microns
        tip : float
            Value in mrad
        tilt : float
            Value in mrad
        addto : str or list, opt.
            Command to stack the one being built on 
            top of. Normally, this will be a flat.
            Can be either a filepath or a list of
            PTT commands.
    '''
    segcommand = [piston, tip, tilt]
    globalcommand = build_global_ptt_command(nsegments)
    globalcommand[n] = segcommand

    if addto is not None:
        if isinstance(addto, str):
            stackwith = read_ptt_command(addto)
        elif isinstance(addto, (list, np.ndarray)):
            stackwith = addto
        else:
            raise TypeError('addto type not recognized. Must be string or list-like.')
        return stack_commands(globalcommand, stackwith)
    else:
        return globalcommand

def build_global_ptt_command(nsegments=37, piston=0., tip=0., tilt=0., addto=None):
    '''
    Build a nsegment-length list of lists containing the [piston, tip, tilt]
    commands to send to each segment of the IrisAO DM.

    Piston = microns
    Tip, tilt = millirad

    If PTT are floats, will be applied globally.
    If they are a list of length nsegments, then
    they'll be applied to the segments individually.

    If no arguments are given, will build the PTT list for a 37-segment
    DM with no PTT applied.

    Parameters:
        nsegments : int
            Number of segments in the IrisAO
        piston : float or list
            Value in microns. If a float, will be applied
            globally. If a list, each segment gets a unique
            value
        tip : float or list
            Value in mrad. See note above.
        tilt : float or list
            Value if mrad. See note above.
        addto : str or list, opt.
            Command to stack the one being built on 
            top of. Normally, this will be a flat.
            Can be either a filepath or a list of
            PTT commands.
    Returns:
        pttlist : list of lists
            An nsegment-length list, each element of which
            is a 3-element list with the piston, tip,
            tilt commands to be applied.
    '''
    pttlist = [[0.,0.,0.] for i in range(nsegments)]

    if isinstance(piston, float):
        for ptt in pttlist:
            ptt[0] = piston
    elif isinstance(piston, (list, tuple, np.ndarray)) and len(piston) == nsegments:
        for ptt, p in zip(pttlist, piston):
            ptt[0] = p
    else:
        raise TypeError('piston is neither a float nor an array-like with length {}!'.format(nsegments))

    if isinstance(tip, float):
        for ptt in pttlist:
            ptt[1] = tip
    elif isinstance(tip, (list, tuple, np.ndarray)) and len(tip) == nsegments:
        for ptt, t in zip(pttlist, tip):
            ptt[1] = t
    else:
        raise TypeError('tip is neither a float nor an array-like with length {}!'.format(nsegments))

    if isinstance(tilt, float):
        for ptt in pttlist:
            ptt[2] = tilt
    elif isinstance(tilt, (list, tuple, np.ndarray)) and len(tilt) == nsegments:
        for ptt, t in zip(pttlist, tilt):
            ptt[2] = t
    else:
        raise TypeError('tilt is neither a float nor an array-like with length {}!'.format(nsegments))

    if addto is not None:
        if isinstance(addto, str):
            stackwith = read_ptt_command(addto)
        elif isinstance(addto, (list, np.ndarray)):
            stackwith = addto
        else:
            raise TypeError('addto type not recognized. Must be string or list-like.')
        return stack_commands(pttlist, stackwith)
    else:
        return pttlist

def stack_commands(pttlist1, pttlist2):
    return [[c1[0] + c2[0],
             c1[1] + c2[1],
             c1[2] + c2[2]]
             for c1, c2 in zip(pttlist1,pttlist2)]

def write_ptt_command(pttlist, outname):
    with open(outname, 'w+') as f:
        writer = csv.writer(f, delimiter=' ', lineterminator='\n')
        writer.writerows(pttlist)

def read_ptt_command(filename):
    with open(filename, 'r') as f:
        reader = csv.reader(f, delimiter=' ', quoting=csv.QUOTE_NONNUMERIC)
        pttlist = [line[:3] for line in reader] # sometimes there's a trailing space
    return pttlist

def twitch_individual_segments(nsegments, ptt=None):
    '''
    Sequentially twitch each individual segment with some
    value(s) of piston/tip/tilt.

    Parameters:
        nsegments : int
            Number of segments
        ptt : tuple, optional.
            If none. Defaults to [0., 1., 0.] -- that is,
            tip each segment. Otherwise, can be set to
            apply some combination of [piston, tip, tilt].
    Returns:
        inputlist : list
            List of PTT commands that can be iteratively applied
            to the mirror.
    '''
    if ptt is None:
        ptt = [0., 1., 0.]

    restcommand = build_global_ptt_command(nsegments)

    inputlist = []
    for n in range(nsegments):
        curcommand = restcommand.copy()
        curcommand[n] = ptt
        inputlist.append(curcommand)

    return inputlist

def test_segment_mode_range(n, nsegments=37, mtype='piston', minval=-1., maxval=1., nval=10.):
    '''
    Generate the input list that will sequentially apply a PTT mode from minval to
    maxval in nval steps.

    Parameters:
        n : int
            Which segment to test?
        nsegments : int, optional
            Total number of segments in the aperture
        mtype : str
            'piston', 'tip', or 'tilt'
        minval : float
            Minimum value to test
        maxval : float
            Maximum value to test
        nval : int
            Number of values between minval and maxval to test.
            Inclusive on both sides of range. 

    Returns:
        inputlist : list
            List of inputs to apply to IrisAO for the requested
            behavior.
    '''
    inputlist = []
    vals = np.linspace(minval, maxval, num=nval, endpoint=True)
    for v in vals:
        inputlist.append(build_segment_command(n, nsegments=nsegments, **{mtype : v}))
    return inputlist

def z_to_xgrad(zcoeff, segdiam=1.212):
    '''
    Assuming Noll-normalized Zernikes.
    The conversion to fringe (value at edge
    of aperture for tip/tilt is *2).

    Then additional factor of 2 to get
    full range over segment.

    Returns gradient (mrad)
    '''
    return (zcoeff * 4.) / (segdiam * 1e3) * 1e3

def z_to_ygrad(zcoeff, segdiam=1.4):
    '''
    Assuming fringe Zernike normalization, where
    the coefficient value is the maximum value at
    the edge of the segment (microns)

    Returns gradient (mrad)
    '''
    return (zcoeff * 4.) / (segdiam * 1e3) * 1e3

def planeslope_to_grad(slope, pixscale=0.017):
    '''
    Given a slope in microns/pix, return it in
    mrad (microns / mm)

    pixscale : mm / pixel
    slope : microns / pix
    '''
    return slope / (pixscale * 1000.) * 1000.

def zcoeffs_to_command(ptt):
    return [ptt[0], -z_to_xgrad(ptt[2]), -z_to_xgrad(ptt[1])]

def planecoeffs_to_command(ptt):
    return [ptt[0], -planeslope_to_grad(ptt[2]), -planeslope_to_grad(ptt[1])]

def segment_mapping(mask):

    segments, nseg = label(mask)
    shape = segments.shape
    ceny, cenx = ((shape[0] - 1) / 2., (shape[1] - 1) / 2.)
    centroids = np.asarray(com(segments > 0, labels=segments, index=np.unique(segments)[1:]))

    xcen = centroids[:, 1]
    column = np.digitize(xcen, np.linspace(xcen.min() - 10., xcen.max() + 10., num=8, endpoint=True), right=True)
    sort = np.lexsort([centroids[:, 0], column])

    irisao_mapping = [23, 24, 25, 26, 22, 10, 11, 12, 27, 21, 9, 3, 4, 13, 28, 20, 8, 2, 1,
                      5, 14, 29, 37, 19, 7, 6, 15, 30, 36, 18, 17, 16, 31, 35, 34, 33, 32]

    newlabel = np.zeros_like(segments)
    for idx, segid in enumerate(np.unique(segments)[1:][sort]):
        newlabel[segments == segid] = irisao_mapping[idx]

    return newlabel

def fit_plane_to_each_segment(segments, surface):
    '''
    Fit PTT plane to each segment on a surface
    and return the plane coefficients as well
    as the corresponding command (the negative
    of which would drive the observed PTT out).
    '''
    fitcoeffs = []
    command = []
    for seg_id in np.unique(segments)[1:]: # skip the background (=0)
        segmask = segments == seg_id
        indices = np.indices(surface.shape)
        # center plane origin on segment center
        ceny, cenx = (int(np.rint(np.mean(indices[0][segmask]))), int(np.rint(np.mean(indices[1][segmask]))))
        indices[0] -= ceny
        indices[1] -= cenx
        fitparams = analysis.fit_plane(surface, segmask, indices)
        command.append(planecoeffs_to_command(fitparams))
        fitcoeffs.append(fitparams)
    return fitcoeffs, command