r"""
Solve Poisson equation in 2D with periodic bcs in one direction
and homogeneous Dirichlet in the other

    \nabla^2 u = f,

Use Fourier basis for the periodic direction and Shen's Dirichlet basis for the
non-periodic direction.

The equation to solve for the Legendre basis is

     (\nabla u, \nabla v) = -(f, v)

whereas for Chebyshev we solve

     (\nabla^2 u, v) = (f, v)

"""
import sys, os
import importlib
from sympy import symbols, cos, sin, lambdify
import numpy as np
from shenfun.fourier.bases import R2CBasis, C2CBasis
from shenfun.tensorproductspace import TensorProductSpace
from shenfun import inner, div, grad, TestFunction, TrialFunction, Function, \
    Array
from mpi4py import MPI
try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

comm = MPI.COMM_WORLD

assert len(sys.argv) == 3, "Call with two command-line arguments"
assert sys.argv[-1] in ('legendre', 'chebyshev')
assert isinstance(int(sys.argv[-2]), int)

# Collect basis and solver from either Chebyshev or Legendre submodules
basis = sys.argv[-1]
shen = importlib.import_module('.'.join(('shenfun', basis)))
Basis = shen.bases.ShenDirichletBasis
Solver = shen.la.Helmholtz

# Use sympy to compute a rhs, given an analytical solution
a = -0
b = 0
x, y = symbols("x,y")
ue = (cos(4*y) + sin(2*x))*(1 - x**2) + a*(1 + x)/2. + b*(1 - x)/2.
fe = ue.diff(x, 2) + ue.diff(y, 2)

# Lambdify for faster evaluation
ul = lambdify((x, y), ue, 'numpy')
fl = lambdify((x, y), fe, 'numpy')

# Size of discretization
N = (int(sys.argv[-2]), int(sys.argv[-2]))

SD = Basis(N[0], scaled=True, bc=(a, b))
K1 = R2CBasis(N[1])
T = TensorProductSpace(comm, (SD, K1), axes=(0, 1))
X = T.local_mesh(True)
u = TrialFunction(T)
v = TestFunction(T)

# Get f on quad points
fj = fl(*X)

# Compute right hand side of Poisson equation
f_hat = Array(T)
f_hat = inner(v, fj, output_array=f_hat)
if basis == 'legendre':
    f_hat *= -1.

# Get left hand side of Poisson equation
if basis == 'chebyshev':
    matrices = inner(v, div(grad(u)))
else:
    matrices = inner(grad(v), grad(u))

# Create Helmholtz linear algebra solver
H = Solver(**matrices)

# Solve and transform to real space
u_hat = Function(T)           # Solution spectral space
u_hat = H(u_hat, f_hat)       # Solve
uq = Function(T, False)
uq = T.backward(u_hat, uq)

# Compare with analytical solution
uj = ul(*X)
assert np.allclose(uj, uq)

if not plt is None and not 'pytest' in os.environ:
    plt.figure()
    plt.contourf(X[0], X[1], uq)
    plt.colorbar()

    plt.figure()
    plt.contourf(X[0], X[1], uj)
    plt.colorbar()

    plt.figure()
    plt.contourf(X[0], X[1], uq-uj)
    plt.colorbar()
    plt.title('Error')

    plt.figure()
    X = T.local_mesh()
    for x in np.squeeze(X[0]):
        plt.plot((x, x), (np.squeeze(X[1])[0], np.squeeze(X[1])[-1]), 'k')
    for y in np.squeeze(X[1]):
        plt.plot((np.squeeze(X[0])[0], np.squeeze(X[0])[-1]), (y, y), 'k')

    plt.show()
