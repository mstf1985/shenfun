"""
Main module for import from shenfun
"""
#pylint: disable=wildcard-import

import numpy as np
from . import chebyshev
from . import legendre
from . import fourier
from . import matrixbase
from .fourier import energy_fourier
from .matrixbase import *
from .forms import *
from .tensorproductspace import *
from .utilities import *
from .utilities.lagrangian_particles import *
from .utilities.integrators import *
from .utilities.shenfun_file import *
from .optimization import Cheb, la, Matvec, convolve, evaluate
