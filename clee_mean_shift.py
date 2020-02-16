"""Meanshift clustering.

Authors: Conrad Lee conradlee@gmail.com
         Alexandre Gramfort alexandre.gramfort@inria.fr
         Gael Varoquaux gael.varoquaux@normalesup.org
"""

from collections import defaultdict
import numpy as np

from sklearn.metrics.pairwise import euclidean_distances
from sklearn.utils import extmath, check_random_state
from sklearn.base import BaseEstimator
from sklearn.neighbors import BallTree

KERNELS = ["flat", "gaussian"]

# Define kernel update functions

def flat_kernel_update(x, points, bandwidth):
    return np.mean(points, axis=0)

def gaussian_kernel_update(x, points, bandwidth):
    distances = euclidean_distances(points, x)
    weights = np.exp(-1 * (distances ** 2 / bandwidth ** 2))
    return np.sum(points * weights, axis=0) / np.sum(weights)

def mean_shift(X, bandwidth=None, seeds=None, kernel="flat",
               max_cluster_radius=-1., max_iterations=300):
    """Perform MeanShift Clustering of data using the specified kernel

    Parameters
    ----------

    X : array [n_samples, n_features]
        Input points to be clustered

    bandwidth : float,
        Kernel bandwidth

    seeds: array [n_seeds, n_features], optional
        Points used as initial kernel locations
        If not set, then use every point as a seed (which may
        be very slow---consider using the `get_bin_seeds` function
        to create a reduced set of seeds.

    max_cluster_radius: float, default -1.
        Used only in post-processing.
        If negative, then each point is clustered into its nearest cluster.
        If positive, then those points that are not within `max_cluster_radius`
        of any cluster center are said to be 'orphans' that do not belong to
        any cluster. Orphans are given cluster label -1.

    Returns
    -------

    cluster_centers : array [n_clusters, n_features]
        Coordinates of cluster centers

    labels : array [n_samples]
        cluster labels for each point

    Notes
    -----
    See examples/plot_meanshift.py for an example.

    """

    if seeds is None:
        seeds = X        
    elif len(seeds) == 0:
        raise ValueError, "If a list of seeds is provided it cannot be empty."

    if not (kernel in KERNELS):
        valid_kernels = " ".join(KERNELS)
        raise ValueError, "Kernel %s is not valid. Valid kernel choices are: %s " % (kernel, valid_kernels)

    # Set maximum neighbor query distance based on kernel
    if kernel in ["flat"]:
        query_distance = bandwidth
        kernel_update_function = flat_kernel_update
        print "Using flat kernel update"
    elif kernel in ["gaussian"]:
        query_distance = bandwidth * 3 # A bit arbitrary
        kernel_update_function = gaussian_kernel_update
        print "Using gaussian kernel update"
    else:
        raise ValueError, "Kernel %s not implemented correctly" % kernel

    n_points, n_features = X.shape
    stop_thresh = 1e-3 * bandwidth  # when mean has converged
    center_intensity_dict = {}
    ball_tree = BallTree(X)  # to efficiently look up nearby points

    # For each seed, climb gradient until convergence or max_iterations
    for weighted_mean in seeds:
        completed_iterations = 0
        while True:
            # Find mean of points within bandwidth
            points_within = X[ball_tree.query_radius([weighted_mean], query_distance)[0]]
            if len(points_within) == 0:
                break  # Depending on seeding strategy this condition may occur
            old_mean = weighted_mean  # save the old mean
            weighted_mean = kernel_update_function(old_mean, points_within, bandwidth)
            # If converged or at max_iterations, addS the cluster
            if extmath.norm(weighted_mean - old_mean) < stop_thresh or \
                   completed_iterations == max_iterations:
                center_intensity_dict[tuple(weighted_mean)] = len(points_within)
                break
            completed_iterations += 1

    # POST PROCESSING: remove near duplicate points
    # If the distance between two kernels is less than the bandwidth,
    # then we have to remove one because it is a duplicate. Remove the
    # one with fewer points.
    print "%d clusters before removing duplicates " % len(center_intensity_dict)
    sorted_by_intensity = sorted(center_intensity_dict.items(),
                                 key=lambda tup: tup[1], reverse=True)
    sorted_centers = np.array([tup[0] for tup in sorted_by_intensity])
    unique = np.ones(len(sorted_centers), dtype=np.bool)
    cc_tree = BallTree(sorted_centers)
    for i, center in enumerate(sorted_centers):
        if unique[i]:
            neighbor_idxs = cc_tree.query_radius([center], bandwidth)[0]
            unique[neighbor_idxs] = 0
            unique[i] = 1  # leave the current point as unique
    cluster_centers = sorted_centers[unique]
    print "%d clusters after removing duplicates " % len(cluster_centers)
    
    # ASSIGN LABELS: a point belongs to the cluster that it is closest to
    centers_tree = BallTree(cluster_centers)
    labels = np.zeros(n_points, dtype=np.int)
    distances, idxs = centers_tree.query(X, 1)
    if max_cluster_radius < 0:
        labels = idxs.flatten()
    else:
        labels[:] = -1
        bool_selector = distances.flatten() <= max_cluster_radius
        labels[bool_selector] = idxs.flatten()[bool_selector]
    return cluster_centers, labels


def get_bin_seeds(X, bin_size, min_bin_freq):
    """Finds seeds for mean_shift

    Finds seeds by first binning data onto a grid whose lines are
    spaced bin_size apart, and then choosing those bins with at least
    min_bin_freq points.

    Parameters
    ----------

    X : array [n_samples, n_features]
        Input points, the same points that will be used in mean_shift

    bin_size: float
        Controls the coarseness of the binning. Smaller values lead
        to more seeding (which is computationally more expensive). If you're
        not sure how to set this, set it to the value of the bandwidth used
        in clustering.mean_shift

    min_bin_freq: integer
        Only bins with at least min_bin_freq will be selected as seeds.
        Raising this value decreases the number of seeds found, which
        makes mean_shift computationally cheaper.

    Returns
    -------
    bin_seeds : array [n_samples, n_features]
        points used as initial kernel posistions in clustering.mean_shift
    """

    # Bin points
    bin_sizes = defaultdict(int)
    for point in X:
        binned_point = np.cast[np.int32](point / bin_size)
        bin_sizes[tuple(binned_point)] += 1

    # Select only those bins as seeds which have enough members
    bin_seeds = np.array([point for point, freq in bin_sizes.iteritems() if \
                          freq >= min_bin_freq], dtype=np.float32)
    bin_seeds = bin_seeds * bin_size
    return bin_seeds


class MeanShift(BaseEstimator):
    """MeanShift clustering

    Parameters
    ----------
    bandwidth: float, optional
        Bandwith used in the RBF kernel
        If not set, the bandwidth is estimated.
        See clustering.estimate_bandwidth

    seeds: array [n_samples, n_features], optional
        Seeds used to initialize kernels. If not specified, every
        point is used as a seed, which can be slow. To speed up
        the algorithm, consider creating a reduced set of seeds using
        the get_binned_seeds function.

    max_cluster_radius: float, default -1.
        Used only in post-processing.
        If negative, then each point is clustered into its nearest cluster.
        If positive, then those points that are not within `max_cluster_radius`
        of any cluster center are said to be 'orphans' that do not belong to
        any cluster. Orphans are given cluster label -1.

    Methods
    -------
    fit(X):
        Compute MeanShift clustering

    Attributes
    ----------
    cluster_centers_: array, [n_clusters, n_features]
        Coordinates of cluster centers

    labels_:
        Labels of each point

    Notes
    -----

    Reference:

    Dorin Comaniciu and Peter Meer, "Mean Shift: A robust approach toward
    feature space analysis". IEEE Transactions on Pattern Analysis and
    Machine Intelligence. 2002. pp. 603-619.

    Scalability:

    Because this implementation uses a flat kernel and
    a Ball Tree to look up members of each kernel, the complexity will is
    to O(T*n*log(n)) in lower dimensions, with n the number of samples
    and T the number of points. In higher dimensions the complexity will
    tend towards O(T*n^2).

    Scalability can be boosted by using fewer seeds, for examply by 
    creating a reduced set of seeds using the get_binned_seeds function
    and using those as the `seeds` argument.


    Note that the estimate_bandwidth function is much less scalable than
    the mean shift algorithm and will be the bottleneck if it is used.
    """
    def __init__(self, bandwidth=None, kernel="flat", seeds=None,
                 max_cluster_radius=-1.):
        self.bandwidth = bandwidth
        self.seeds = seeds
        self.max_cluster_radius = max_cluster_radius
        self.cluster_centers_ = None
        self.labels_ = None
        self.kernel = kernel

    def fit(self, X):
        """ Compute MeanShift

        Parameters
        -----------
        X : array [n_samples, n_features]
            Input points
        """
        self.cluster_centers_, self.labels_ = \
                               mean_shift(X,
                                          bandwidth=self.bandwidth,
                                          kernel = self.kernel,
                                          seeds=self.seeds,
                                          max_cluster_radius=self.max_cluster_radius)
        return self
