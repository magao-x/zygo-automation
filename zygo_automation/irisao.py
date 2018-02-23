import csv
import subprocess
import numpy as np

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
    subprocess.call(['sh', 'SendPTT', mserial, dserial, str(int(hardware_disable)), pttfile],
                     cwd=script_path)

def release_mirror(mserial='PWA37-05-04-0404', dserial='09150004',
                   script_path='/home/lab/IrisAO/SourceCodes', hardware_disable=False):
    # run Alex's C code (needs to have root privileges...)
    subprocess.call(['sh', 'Release', mserial, dserial], cwd=script_path)

def flatten_mirror(mserial='PWA37-05-04-0404', dserial='09150004',
                   script_path='/home/lab/IrisAO/SourceCodes', hardware_disable=False):
    # run Alex's C code (needs to have root privileges...)
    subprocess.call(['sh', 'Flatten2', mserial, dserial], cwd=script_path)

def build_global_zmode():
    '''
    Magic happens here. I don't even know if I want to do this, or if I
    just want to use IrisAO's prebuilt global modes.
    '''
    pass

def build_segment_command(n, nsegments=37, piston=0., tip=0., tilt=0.):
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
    '''
    segcommand = [piston, tip, tilt]
    globalcommand = build_global_ptt_command(nsegments)
    globalcommand[n] = segcommand
    return globalcommand

def build_global_ptt_command(nsegments=37, piston=0., tip=0., tilt=0.):
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

    return pttlist

def write_ptt_command(pttlist, outname):
    with open(outname, 'w+') as f:
        writer = csv.writer(f, delimiter=' ', lineterminator='\n')
        writer.writerows(pttlist)

def read_ptt_command(filename):
    with open(filename, 'r') as f:
        reader = csv.reader(f, delimiter=' ', quoting=csv.QUOTE_NONNUMERIC)
        pttlist = [line for line in reader]
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
