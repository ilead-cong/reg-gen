#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Created on Mar 6, 2013

@author: manuel
'''
from __future__ import print_function
from scipy.stats import binom
from hmmlearn.hmm import _BaseHMM
import string , numpy as np
from time import time
from math import fabs
#from help_hmm import _init, _add_pseudo_counts, _valid_posteriors
# import cProfile
from help_hmm import _valid_posteriors, _count
import sys
from rgt.ODIN.help_hmm import _add_pseudo_counts

def get_init_parameters(s1, s2, **info):
    n_ = np.array([info['count'], info['count']])
    #get observation that occurs most often:
    m_ =[float(np.argmax(np.bincount(map(lambda x: x[0], s1)))), float(np.argmax(np.bincount(map(lambda x: x[1], s2)))) ]
    p_ = [[-1,-1,-1],[-1,-1,-1]] #first: 1. or 2. emission, second: state
    
    p_[0][0] = 1. / n_[0]
    p_[1][0] = 1. / n_[1]
    p_[0][1] = m_[0] / n_[0]
    p_[1][1] = p_[1][0]
    p_[0][2] = p_[0][0]
    p_[1][2] = m_[1] / n_[1]
    
    return np.asarray(n_), np.asarray(p_)

class BinomialHMM(_BaseHMM):
    def __init__(self, n, p, dim_cond_1, dim_cond_2, init_state_seq=None, n_components=2, covariance_type='diag', startprob=None,
                 transmat=None, startprob_prior=None, transmat_prior=None,
                 algorithm="viterbi", means_prior=None, means_weight=0,
                 covars_prior=1e-2, covars_weight=1,
                 random_state=None, n_iter=10, thresh=1e-2,
                 params=string.ascii_letters,
                 init_params=string.ascii_letters):
    
        _BaseHMM.__init__(self, n_components, startprob, transmat,
                          startprob_prior=startprob_prior,
                          transmat_prior=transmat_prior, algorithm=algorithm,
                          random_state=random_state, n_iter=n_iter,
                          thresh=thresh, params=params,
                          init_params=init_params)
        
        self.dim = [dim_cond_1, dim_cond_2] #dimension of one emission
        self.n = n
        self.p = p
        self.n_features = 2 #emission dimension
        self.init_state_seq = init_state_seq
        self.count_s1, self.count_s2 = 0, 0
        self.lookup_logpmf = {}

    def _compute_log_likelihood(self, X):
        res = []
        
        for x in X: #over all observations
            row = []
            for i in range(self.n_components): #over number of HMM's state
                r_sum = 0
                for j in range(self.n_features): #over dim
                    it = range(self.dim[0]) if j == 0 else range(self.dim[0], self.dim[0] + self.dim[1]) #grab proper observation
                    for k in it:
                        index = (int(x[k]), self.p[j][i], self.n[j])
                        if not self.lookup_logpmf.has_key( index ):
                            self.lookup_logpmf[index] = binom.logpmf(x[k], self.n[j], self.p[j][i])
                        r_sum += self.lookup_logpmf[index]
                row.append(r_sum)
        
            res.append(row)
        
        return np.asarray(res)
    

    def _generate_sample_from_state(self, state, random_state=None):
        output = []
        for i, d in enumerate(self.dim):
            for _ in range(d):
                output.append( binom.rvs(self.n[i], self.p[i][state]) )
        
        return np.asarray(output)
        
            
    def _initialize_sufficient_statistics(self):
        stats = super(BinomialHMM, self)._initialize_sufficient_statistics()
        stats['post'] = np.zeros([self.n_components])
        stats['post_emission'] = np.zeros([self.n_features, self.n_components])
        return stats
    
    def _help_accumulate_sufficient_statistics(self, obs, stats, posteriors):
        for t, symbol in enumerate(obs):
            pot_it = [range(self.dim[0]), range(self.dim[0], self.dim[0] + self.dim[1])] #consider both classes
            for j, it in enumerate(pot_it):
                for i in it:
                    stats['post'] += posteriors[t]
                    stats['post_emission'][j] += posteriors[t] * symbol[i]
            
        stats['posterior'] = np.copy(posteriors)
         
    def _accumulate_sufficient_statistics(self, stats, obs, framelogprob,
                                      posteriors, fwdlattice, bwdlattice,
                                      params):
        super(BinomialHMM, self)._accumulate_sufficient_statistics(
            stats, obs, framelogprob, posteriors, fwdlattice, bwdlattice,
            params)
        
        posteriors = _valid_posteriors(posteriors, obs, self.dim)
        self._help_accumulate_sufficient_statistics(obs, stats, posteriors)        
    
    
    def _help_do_mstep(self, stats):
        for i in range(self.n_features):
            self.p[i] = stats['post_emission'][i] / (self.n[i] * _add_pseudo_counts(stats['post']))
            print('help_m_step', i, stats['post_emission'][i], stats['post'], self.p[i], file=sys.stderr)
        
    def _do_mstep(self, stats, params):
        super(BinomialHMM, self)._do_mstep(stats, params)
        self._help_do_mstep(stats)
        self._merge_distr(stats['posterior'])
        
    
    def _merge_distr(self, posterior):
        count_s1, count_s2 = _count(posterior)
        f = count_s2 / float(count_s1 + count_s2)
        
        high = min(self.p[0,1], self.p[1,2]) + f * fabs(self.p[0,1] - self.p[1,2])
        low = min(self.p[1,1], self.p[0,2]) + f * fabs(self.p[1,1] - self.p[0,2])
        #med = np.mean([el[0,0], el[1,0]])
        
        self.p[0,1], self.p[1,2] = high, high
        self.p[1,1], self.p[0,2] = low, low
        self.p[0,0], self.p[1,0] = low, low #min(med, low)
        


if __name__ == '__main__':
    p_ = np.array([[0.01, 0.8, 0.1], [0.01, 0.1, 0.8]])
    n_ = np.array([100, 100])
    
    m = BinomialHMM(n_components=3, p = p_, startprob=[1,0,0], n = n_, dim_cond_1=2, dim_cond_2=4)
    
    X, Z = m.sample(100) #returns (obs, hidden_states)
    
    p_ = np.array([[0.1, 0.7, 0.3], [0.1, 0.2, 0.9]])
    n_ = np.array([100, 100])
    
    m2 = BinomialHMM(n_components=3, n=n_, p=p_, dim_cond_1=2, dim_cond_2=4)
    #cProfile.run("m2.fit([X])")
    
    m2.fit([X])
    e = m2.predict(X)
    print(m2.p)
    for i, el in enumerate(X):
        print(el, Z[i], e[i], Z[i] == e[i], sep='\t')
    
#    logprob, posteriors = m2.eval(X)
#    print('logprob:', logprob)
#    print('posteriors:', posteriors)
    
#     print('estim. states ', m2.predict(X))
#     print(m2.predict_proba(X))
#     print(m2.n)
#     print(m2.p)
#     print(m2._get_transmat())
#     init_state = m2.predict(X)
#     m3 = BinomialHMM2d3s(n_components=3, n=n_)
#     m3.fit([X], init_params='advanced')
#     print(m3._get_transmat())
#     print(m3.p)
#     m2.eval(X)
    