#!/usr/bin/env python
#-*- coding: utf-8 -*-

import sys, argparse
import numpy as np
from scipy.sparse import lil_matrix, vstack

from hicexplorer import HiCMatrix as hm
from hicexplorer.reduceMatrix import reduce_matrix
from hicexplorer._version import __version__

debug = 0

def parseArguments(args=None):

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='Merges bins from a Hi-Cmatrix. For example, '
        'using a matrix containing 5bk bins, a matrix '
        'of 50 kb bins can be derived. ')

    # define the arguments
    parser.add_argument('--matrix', '-m',
                        help='Matrix to reduce.',
                        metavar='.npz fileformat',
                        required=True)

    parser.add_argument('--numBins', '-nb',
                        help='Number of bins to merge.',
                        metavar='int',
                        type=int,
                        required=True)

    parser.add_argument('--runningWindow',
                        help='set to merge for using a running '
                        'window of length --numBins',
                        action='store_true')

    parser.add_argument('--outFileName', '-o',
                        help='File name to save the resulting matrix. '
                        'The output is also a .npz file. But don\'t add '
                        'the suffix', 
                        required=True)

    parser.add_argument('--version', action='version',
                        version='%(prog)s {}'.format(__version__))


    return(parser.parse_args(args))

def running_window_merge(hic_matrix):
    """Creates a 'running window' merge. If the original matrix
    has bins as 5000 resolution the output matrix also has 5000 resolution.
    However, each element of the matrix is the sum of the 4 neighboring
    regions. For the followin matrix, the sums are as follows: a+b+d+e,
    b+c+d+f etc.

       a | b | c
       ---------
       d | e | f
       ---------
       g | h | i


    >>> from scipy.sparse import csr_matrix
    >>> row, col = np.triu_indices(5)
    >>> cut_intervals = [('a', 0, 10, 0.5), ('a', 10, 20, 1),
    ... ('a', 20, 30, 1), ('a', 30, 40, 0.1), ('b', 40, 50, 1)]
    >>> hic = hm.hiCMatrix()
    >>> hic.nan_bins = []
    >>> matrix = np.array([
    ... [ 0, 10,  5, 3, 0],
    ... [ 0,  0, 15, 5, 1],
    ... [ 0,  0,  0, 7, 3],
    ... [ 0,  0,  0, 0, 1],
    ... [ 0,  0,  0, 0, 0]])

    make the matrix symmetric:
    >>> hic.matrix = csr_matrix(matrix + matrix.T)
    >>> hic.setMatrix(csr_matrix(matrix + matrix.T), cut_intervals)
    >>> merge_matrix = running_window_merge(hic)
    >>> merge_matrix.cut_intervals
    [('a', 5, 15, 0.75), ('a', 15, 25, 1.0), ('a', 25, 35, 0.55000000000000004)]
    >>> merge_matrix.matrix.todense()
    matrix([[20, 30, 28],
            [30, 30, 27],
            [28, 27, 14]])
    """

    from scipy.sparse import csr_matrix, vstack, hstack

    num_rows = num_cols = hic_matrix.matrix.shape[0]
    # add an extra last row the original matrix
    rows_mat = csr_matrix((num_rows, 1))
    merge_matrix = hstack([hic_matrix.matrix, rows_mat])
    # add an extra last column to the original matrix
    cols_mat = csr_matrix((1, num_cols + 1))
    merge_matrix = vstack([merge_matrix, cols_mat],
                          format='coo').astype(int)


    #merge_matrix = hic_matrix.matrix.tocoo()

    # merge matrix is equal to merge_matrix + down + right + down_right
    # where down is the same matrix but all rows are +1,
    # for right, all cols are +1 and for down_right, cols and rows are
    # +1
    down = merge_matrix.copy()
    down.row = down.row + 1

    right = merge_matrix.copy()
    right.col = right.col + 1

    down_right = down.copy()
    down_right.col = down_right.col + 1

    merge_matrix = (merge_matrix + down + right + down_right).tocsr()
    # new matrix is one row and one column bigger, which need to be
    # removed
    merge_matrix = merge_matrix[1:, :][:, 1:]

    # not the intervals need to be adjusted.
    # the original interval 'chr1', 0, 5000' needs
    # to be rewritten as 'chr1', 2500, 7500
    bin_size_half = int(hic_matrix.getBinSize() / 2)
    to_keep = []
    total_intervals = len(hic_matrix.cut_intervals)
    new_intervals = []
    for idx, interval in enumerate(hic_matrix.cut_intervals):
        chrom, start, end, coverage = interval
        if idx + 1 >= total_intervals:
            continue
        if chrom != hic_matrix.cut_intervals[idx+1][0]:
            # the next interval is for a different
            # chromosome. That means, this region has
            # to be removed
            continue
        to_keep.append(idx)
        coverage = np.mean([coverage, hic_matrix.cut_intervals[idx+1][-1]])
        new_intervals.append((chrom, start + bin_size_half,
                        end + bin_size_half, coverage))


    hic_matrix.matrix = merge_matrix[to_keep, :][:, to_keep]
    hic_matrix.cut_intervals = new_intervals
    hic_matrix.nan_bins = np.flatnonzero(hic_matrix.matrix.sum(0).A == 0)

    return hic_matrix

def running_window_merge_v2(hic_matrix, num_bins):
    """Creates a 'running window' merge without changing the
    original resolution of the matrix. The window size is
    defined by the num_bins that are merged. Num bins
    had to be an odd number such that equal amounts of left and 
    right bins can be merged.

       a | b | c
       ---------
       d | e | f
       ---------
       g | h | i

    In this matrix, using a merge of num_bins 3, 
    the merge is done as follows, a = a + b + d + e,
    e = a + b + c + d + e + f etc,

    >>> from scipy.sparse import csr_matrix, dia_matrix
    >>> row, col = np.triu_indices(5)
    >>> cut_intervals = [('a', 0, 10, 0.5), ('a', 10, 20, 1),
    ... ('a', 20, 30, 1), ('a', 30, 40, 0.1), ('b', 40, 50, 1)]
    >>> hic = hm.hiCMatrix()
    >>> hic.nan_bins = []
    >>> matrix = np.array([
    ... [ 1, 1 ],
    ... [ 1, 1 ]])

    make the matrix symmetric:
    >>> hic.matrix = csr_matrix(matrix)
    >>> hic.setMatrix(hic.matrix, cut_intervals)
    >>> merge_matrix = running_window_merge_v2(hic, 3)
    >>> merge_matrix.matrix.todense()
    matrix([[3, 3],
            [3, 3]])

    >>> matrix = np.array([
    ... [ 1, 1, 1, 1 ],
    ... [ 1, 1, 1, 1 ],
    ... [ 1, 1, 1, 1 ],
    ... [ 1, 1, 1, 1 ]])

    make the matrix symmetric:
    >>> hic.matrix = csr_matrix(matrix)
    >>> hic.setMatrix(hic.matrix, cut_intervals)
    >>> merge_matrix = running_window_merge_v2(hic, 3)
    >>> merge_matrix.matrix.todense()
    matrix([[3, 5, 6, 4],
            [5, 6, 8, 6],
            [6, 8, 6, 5],
            [4, 6, 5, 3]])
    """

    if num_bins == 1:
        return hic_matrix

    assert num_bins % 2 == 1, "num_bins has to be an odd number"
    half_num_bins = int((num_bins-1) /2)
    from scipy.sparse import coo_matrix, vstack, hstack, dia_matrix, triu
    M = hic_matrix.matrix.shape[0]
    ma = triu(hic_matrix.matrix, k=0, format='coo')
    row = ma.row
    col = ma.col
    data = ma.data
    # indices list:
    idx_list = []
    for i in range(num_bins):
        for j in range(num_bins):
            idx_list.append((j-half_num_bins, i-half_num_bins))

    new_row = row
    new_col = col
    new_data = data
    for idx_pair in idx_list:
        if idx_pair == (0,0): continue
        new_row = np.concatenate([new_row, row + idx_pair[0]])
        new_col = np.concatenate([new_col, col + idx_pair[1]])
        new_data = np.concatenate([new_data, data])

#    import ipdb;ipdb.set_trace()
#    print np.vstack([new_row, new_col, new_data])

    # remove illegal matrix id
    # that are less than zero
    # or bigger than matrix size
    keep = ((new_row  > -1) & (new_col >-1) & 
            (new_row  < M ) & (new_col < M))
    new_data =new_data[keep]
    new_row = new_row[keep]
    new_col = new_col[keep]
    
    new_ma = coo_matrix((new_data, (new_row, new_col)), shape=(M, M))
    new_ma = triu(new_ma, k=0)
 #   new_ma.data = new_ma.data / len(idx_list)
    dia = dia_matrix(([new_ma.diagonal()], [0]), shape=new_ma.shape)
    new_ma = new_ma + new_ma.T - dia

    hic_matrix.matrix = new_ma
    hic_matrix.nan_bins = np.flatnonzero(hic_matrix.matrix.sum(0).A == 0)

    return hic_matrix

def merge_bins(hic, num_bins):
    """
    >>> from scipy.sparse import csr_matrix
    >>> row, col = np.triu_indices(5)
    >>> cut_intervals = [('a', 0, 10, 0.5), ('a', 10, 20, 1),
    ... ('a', 20, 30, 1), ('a', 30, 40, 0.1), ('b', 40, 50, 1)]
    >>> hic = hm.hiCMatrix()
    >>> hic.nan_bins = []
    >>> matrix = np.array([
    ... [ 50, 10,  5,  3,   0],
    ... [  0, 60, 15,  5,   1],
    ... [  0,  0, 80,  7,   3],
    ... [  0,  0,  0, 90,   1],
    ... [  0,  0,  0,  0, 100]])


    make the matrix symmetric:
    >>> from scipy.sparse import coo_matrix, dia_matrix

    >>> dia = dia_matrix(([matrix.diagonal()], [0]), shape=matrix.shape)
    >>> hic.matrix = csr_matrix(matrix + matrix.T - dia)
    >>> hic.setMatrix(csr_matrix(matrix + matrix.T), cut_intervals)
    >>> merge_matrix = merge_bins(hic, 2)
    >>> merge_matrix.cut_intervals
    [('a', 0, 20, 0.75), ('a', 20, 40, 0.55000000000000004), ('b', 40, 50, 1.0)]
    >>> merge_matrix.matrix.todense()
    matrix([[120,  28,   1],
            [ 28, 177,   4],
            [  1,   4, 100]])
    """
    # get the bins to merge
    ref_name_list, start_list, end_list, coverage_list = \
        zip(*hic.cut_intervals)
    new_bins = []
    bins_to_merge = []
    prev_ref = ref_name_list[0]

    # prepare new intervals
    idx_start = 0
    new_start = start_list[0]
    count = 0
    for idx, ref in enumerate(ref_name_list):
        if (count > 0 and count % num_bins == 0) or ref != prev_ref:
            coverage = np.mean(coverage_list[idx_start:idx])
            new_bins.append((ref_name_list[idx_start], new_start,
                             end_list[idx-1], coverage))
            bins_to_merge.append(range(idx_start, idx))
            idx_start = idx
            new_start = start_list[idx]
            count = 0 

        prev_ref = ref
        count += 1
    coverage = np.mean(coverage_list[idx_start:])
    new_bins.append((ref, new_start, end_list[idx], coverage))
    bins_to_merge.append(range(idx_start, idx+1))

    hic.matrix = reduce_matrix(hic.matrix, bins_to_merge, diagonal=True)
    hic.cut_intervals = new_bins
    hic.nan_bins = np.flatnonzero(hic.matrix.sum(0).A == 0)

    return hic


def main(args):

    hic = hm.hiCMatrix(args.matrix)
    if args.runningWindow:
        merged_matrix = running_window_merge_v2(hic, args.numBins)
    else:
        merged_matrix = merge_bins(hic, args.numBins)

    print 'saving matrix'
    # there is a pickle problem with large arrays
    # To increase the sparsity of the matrix and
    # overcome the problem
    # I transform al ones into zeros.
    """
    merged_matrix.matrix.data = merged_matrix.matrix.data - 1
    """
    merged_matrix.matrix.eliminate_zeros()

    merged_matrix.save(args.outFileName)


if __name__ == "__main__":
    args = parseArguments()
    main(args)
