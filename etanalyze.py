#!/opt/local/bin/python2.7
"""
This program takes as input an eye tracking csv file and outputs weighted clusters of fixations

Call:
    etanalyse etfile[.csv]

Will produce files etfile.frames.csv and etfile.clusters.csv

(c) 2014 Per Baekgard, pgba@dtu.dk

"""

import math
import numpy as np
import csv
import clee_mean_shift as ms
import sys
import getopt
from mpl_toolkits.mplot3d import Axes3D
from itertools import cycle

import mpld3

# Configurable values -- can also be used from the command line
min_fix = 0.100
min_cluster_size = 50.0
screenx = 1440
screeny = 900
frame_res = 30.0

# Derived value(s)
min_fix_pts = round(min_fix * frame_res)

def spat_dist(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

def cluster_frames_exp(npeyeframes):
    '''
    TODO: Algo to be implemented
        gaussian_mean(frames, center, min, max):
            # apply kernel centered over center from min to max
            # make sure to discard items "too far away" from the spatial position

        clustered_frames = npeyeframes:
            l = len(npeyeframes)
            prev_frames = clustered_frames
            max_iter = 300
            while max_item-- > 0:
                for i in range(l):
                    min, max = i-window, i+window # need to find out what min and max are)
                    clustered_frames[i] = gaussian_mean(prev_frames, i, min, max)

                if # clustered_frames - prev_frames is small:
                    break

            # remove near-identical points

    '''
    return ((), ())

def cluster_frames_DBSCAN(npeyeframes):
    '''
    Cluster frames with a derivate of DBSCAN taking into account the time
    
    This DBSCAN variation uses DBSCAN in the local spatial neighbourhood with timing constraints:
    Single or a few outliers followed by additional connected points are considered noise, 
    and more points can be added to the current cluster
    However if enough disjoint points are seen that could make up a cluster (temporally!) it ends the current cluster
    '''

    def query_region(frames, first, reference):
        '''returns absolute indices of frames in neighbourhood of reference, from first to break/len(frames)'''
        i = first
        region = set()
        seq_outside = 0
        while i < len(frames):
            if spat_dist(frames[reference], npeyeframes[i]) < min_cluster_size:
                region.add(i)
                seq_outside = 0
            else:
                if i > reference:
                    seq_outside += 1
                    if seq_outside >= min_fix_pts:
                        break
            i += 1
        return region


    # first create labels; 0 means unassigned (so far)
    labels = np.zeros(len(npeyeframes), dtype=int)

    label = 1
    unassigned = 0
    nextp = unassigned
    while nextp < len(labels):
        print ("DBSCAN index %d" % nextp)
        if labels[nextp] == 0:
            neighbours = query_region(npeyeframes, unassigned, nextp)
            if len(neighbours) < min_fix_pts:
                print ("   Too few neighbours; leaving point alone: %d" % len(neighbours))
            else:
                print ("   New cluster: %d [Initial: %d]" % (label, len(neighbours)))
                unvisited = neighbours
                unvisited.remove(nextp)
                visited = set()
                visited.add(nextp)

                while len(unvisited) > 0:
                    first = unvisited.pop()

                    visited.add(first)
                    neighbours = query_region(npeyeframes, unassigned, first)
                    if len(neighbours) >= min_fix_pts:  # SHOULD THIS BE > 0 only?
                        unvisited.update(neighbours - visited)

                for v in visited:
                    assert labels[v] == 0, "Reassigning point to new cluster, should not take place"
                    labels[v] = label
                    nextp = max(nextp, v)

                unassigned = nextp + 1
                label += 1
                print ("   Next unassigned: %d [Final: %d]" % (unassigned, len(visited)))
        else:
            print ("   Already assigned to %d" % labels[nextp])

        nextp += 1

    # remove any empty last cluster
    if len(npeyeframes[labels==label])==0:
        print ("   Last cluster (%d) is empty, removing" % (label))
        label -= 1

    # calculate the cluster centers...
    print ("   Ended up with %d clusters" % label)
    cluster_centers = np.empty([label+1, 3*4])
    for l in range(label+1):
        # print ("   Fixing frames in  clusters %d" % l)

        myframes = npeyeframes[labels==l]
        mylen = len(myframes)
        if (mylen > 0):
            cmean = np.mean(myframes, 0)
            cmin = np.amin(myframes, 0)
            cmax = np.amax(myframes, 0)
            cstd = np.std(myframes, 0)
            cluster_centers[l] = np.concatenate((cmean, cmin, cmax, cstd))

    return (labels, cluster_centers)

def cluster_frames(npeyeframes):
    '''
    Cluster the npeyeframes that each have (x,y,t) positions; need not be equitemporally sampled
    
    Returns a tupple of labels and centers
    where len(labels)==len(npeyeframes), and labels[i] is index into clusters for frame i
    and centers contains the (x,y,t) coordinates of each cluster found
    '''

    return cluster_frames_DBSCAN(npeyeframes)

USAGE = "Usage:\n   %s [--minfix <time>] [--mincluster <pixels>] [--screenx <pixels>]\n      [--screeny <pixels>] [--frameres <time>] etanalyze[.csv]\n"

try:
    options, args = getopt.getopt(sys.argv[1:], '', ['minfix=', 'mincluster=', 'screenx=', 'screeny=', 'frameres='])
except getopt.GetoptError as err:
    sys.stderr.write(USAGE % sys.argv[0])
    sys.exit(2)

for o, a in options:
    if o in ('--minfix'):
        min_fix = float(a)
    elif o in ('--mincluster'):
        min_cluster_size = float(a)
    elif o in ('--screenx'):
        screenx = int(a)
    elif o in ('--screeny'):
        screeny = int(a)
    elif o in ('--frameres'):
        frame_res = float(a)
    elif o in ('--help'):
        sys.stderr.write(USAGE % sys.argv[0])

if len(args) != 1:
    sys.stderr.write(USAGE % sys.argv[0])
    exit(1)

datafilename = args[0].replace(".csv","")
outfilename = datafilename.split('/')[-1]

# Read eyeframe data from input file
eyeframes = []  # eyeframes as (x, y, t) tupples
blinks = []  # blinks as (t, dur) tupples
offset = None
with open(datafilename+".csv", 'rU') as csvfile:
    rows = csv.DictReader(csvfile, delimiter=';')
    blinkStart = None
    for row in rows:
        if offset is None:
            offset = float(row['aT'])
        time = (float(row['aT'])-offset)*min_cluster_size/min_fix
        if 'G' in row['State']:
            if blinkStart:
                print ("BLINK end at %s (%.3f); len becomes %.3f" % (row['aT'], time/min_cluster_size*min_fix, (time-blinkStart)/min_cluster_size*min_fix))
                blinks.append((blinkStart, time-blinkStart))
                blinkStart = None

            x = float(row['Rwx'])
            y = float(row['Rwy'])
            if x < 0 or x > screenx:
                next
            if y < 0 or y > screeny:
                next
            eyeframes.append((float(row['Rwx']), float(row['Rwy']), time))
        else:
            if not blinkStart:
                print ("BLINK start at %s (%.3f)" % (row['aT'], time/min_cluster_size*min_fix))
                blinkStart = time
    if blinkStart:
        blinks.append((blinkStart, time-blinkStart+1.0/frame_res))
        blinkStart = None

npeyeframes = np.array(eyeframes)

# Cluster the data into and centers and labels
labels, cluster_centers = cluster_frames(npeyeframes)

labels_unique = np.unique(labels)
n_clusters = len(labels_unique)

assert n_clusters == len(cluster_centers) or n_clusters == len(cluster_centers)-1,\
    "Weird, we got %d unique labels but %d clusters returned..." % (n_clusters, len(cluster_centers))

# ... and print them out
cof = open(outfilename+".clusters.csv", "w")
cof.write("x;y;tmin;tmean;tmax;c;z;n\n")
for k in labels_unique:
    my_members = labels == k
    cluster_center = cluster_centers[k]
    myframes = npeyeframes[my_members]
    if len(myframes) > 1:
        offsets = np.linalg.norm(myframes[:,0:2]-cluster_center[0:2], axis=1)
        # csize = np.sqrt(np.mean(offsets**2))
        csize = max(offsets)
    else:
        csize = 1

    # Values are x, y, tmin, tmean, tmax, cluster_id, cluster_size, #members_in_cluster
    if (k!=0):
        cof.write('%d;%d;%.3f;%.3f;%.3f;%d;%.3f;%d\n' % 
                (cluster_center[0], cluster_center[1], 
                    cluster_center[5]/min_cluster_size*min_fix, 
                    cluster_center[2]/min_cluster_size*min_fix, 
                    cluster_center[8]/min_cluster_size*min_fix, 
                    k-1, csize, len(myframes)))
cof.close()

# print out frames, relabeling their assigned clusters (so assigned are from 0 to ... and unassigned is -1)
fof = open(outfilename+".frames.csv", "w")
fof.write("x;y;t;c\n")
maxcl = -1
for x, y, t, cl in zip(npeyeframes[:,0], npeyeframes[:,1], npeyeframes[:,2], labels):
    # Values are x, y, t, cluster_id
    fof.write('%d;%d;%.3f;%d\n' % (x, y, t/min_cluster_size*min_fix, cl-1))
    if cl!=0:
        assert cl >= maxcl, "Error in clustering, decrementing cluster count (%d after %d)" % (cl, maxcl)
        maxcl = max(cl, maxcl)

fof.close()

# finally, print out blinks (or non-detects or whatever they are)
bof = open(outfilename+".blinks.csv", "w")
bof.write("t;dur\n")
for t, dur in blinks:
    # Values are time, duration
    bof.write('%.3f;%.3f\n' % (t/min_cluster_size*min_fix, dur/min_cluster_size*min_fix))
bof.close()

