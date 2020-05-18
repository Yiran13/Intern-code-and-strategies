from numba import jit
import numpy as np  

x = np.arange(100).reshape(10,10)

@jit(nopython=True)
def go_fast(a):
    trace = 0.0
    for i in range(a.shape[0]):  # numba likes loop
        trace += np.tanh(a[i,i]) # numba likes numpy functions
    return a + trace


print(go_fast(x))