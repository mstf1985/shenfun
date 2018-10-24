#pylint: disable=missing-docstring,consider-using-enumerate
import warnings
import copy
import numpy as np
from mpi4py_fft.utilities import NCFile as BaseFile
from .shenfun_file import write_vector

# https://github.com/Unidata/netcdf4-python/blob/master/examples/mpi_example.py

__all__ = ('NCFile',)


class NCFile(BaseFile):
    """Class for reading/writing data using the netCDF4 format

    Parameters
    ----------
        ncname : str
                 Name of netcdf file to be created
        T : TensorProductSpace
            Instance of a :class:`.TensorProductSpace`. Can also be a
            :class:`.MixedTensorProductSpace`.
        mode : str, optional
            ``r`` or ``w`` for read or write. Default is ``r``.
        clobber : bool, optional
    """
    def __init__(self, ncname, T, mode='r', clobber=True, **kw):
        BaseFile.__init__(self, ncname, T, domain=T.mesh(), clobber=clobber, mode=mode, **kw)
        if T.rank() == 2 and mode == 'w':
            self.vdims = copy.copy(self.dims)
            self.f.createDimension('dim', T.num_components())
            d = self.f.createVariable('dim', int, ('dim'))
            d[:] = np.arange(T.num_components())
            self.vdims.insert(1, 'dim')

    def write(self, step, fields, **kw):
        """Write snapshot ``step`` of ``fields`` to netCDF4 file

        Parameters
        ----------
        step : int
            Index of snapshot.
        fields : dict
            The fields to be dumped to file. (key, value) pairs are group name
            and either arrays or 2-tuples, respectively. The arrays are complete
            arrays to be stored, whereas 2-tuples are arrays with associated
            *global* slices.
        as_scalar : bool, optional
            Whether to store vectors as scalars. Default is False.

        Example
        -------
        >>> from mpi4py import MPI
        >>> import numpy as np
        >>> from shenfun import TensorProductSpace, Array, Basis
        >>> from shenfun.utilities import NCFile
        >>> comm = MPI.COMM_WORLD
        >>> N = (24, 25, 26)
        >>> K0 = Basis(N[0], 'F', dtype='D')
        >>> K1 = Basis(N[1], 'F', dtype='D')
        >>> K2 = Basis(N[2], 'F', dtype='d')
        >>> T = TensorProductSpace(comm, (K0, K1, K2))
        >>> fl = NCFile('ncfile.nc', T, mode='w')
        >>> u = Array(T)
        >>> u[:] = np.random.random(T.forward.input_array.shape)
        >>> d = {'u': [u, (u, np.s_[4, :, :]), (u, np.s_[4, 4, :])]}
        >>> fl.write(0, d)
        >>> u[:] = 2
        >>> fl.write(1, d)
        >>> fl.close()

        The resulting NetCDF4 file ``ncfile.nc`` can be viewed using
        ``ncdump -h ncfile.nc``::

            netcdf ncfile {
            dimensions:
                    time = UNLIMITED ; // (2 currently)
                    x = 24 ;
                    y = 25 ;
                    z = 26 ;
            variables:
                    double time(time) ;
                    double x(x) ;
                    double y(y) ;
                    double z(z) ;
                    double u(time, x, y, z) ;
                    double u_4_slice_slice(time, y, z) ;
                    double u_4_4_slice(time, z) ;

            // global attributes:
                            :ndim = 3LL ;
                            :shape = 24LL, 25LL, 26LL ;
            }

        """
        as_scalar = kw.get('as_scalar', False)
        if self.T.rank() == 1 or (not as_scalar):
            BaseFile.write(self, step, fields, **kw)
        else:
            it = self.nc_t.size
            self.nc_t[it] = step
            write_vector(self, it, fields, **kw)

    def _write_group(self, name, u, step, **kw):
        as_scalar = kw.get('as_scalar', False)
        T = self.T if not as_scalar else self.T[0]
        s = T.local_slice(False)
        dims = self.dims if T.rank() == 1 else self.vdims
        if name not in self.handles:
            self.handles[name] = self.f.createVariable(name, self._dtype, dims)
            self.handles[name].set_collective(True)
        s = tuple([step] + s)
        self.handles[name][s] = u
        self.f.sync()

    def _write_slice_step(self, name, step, slices, field, **kw):
        as_scalar = kw.get('slice_as_scalar', False)
        slices = list(slices)
        T = self.T if not as_scalar else self.T[0]
        if T.rank() == 2:
            slname = self._get_slice_name(slices[1:])
        else:
            slname = self._get_slice_name(slices)

        dims = self.dims if T.rank() == 1 else self.vdims
        s = T.local_slice(False)
        slices, inside = self._get_local_slices(slices, s)
        sp = np.nonzero([isinstance(x, slice) for x in slices])[0]
        sf = np.take(s, sp)
        sdims = ['time'] + list(np.take(dims, np.array(sp)+1))
        fname = "_".join((name, slname))
        if fname not in self.handles:
            self.handles[fname] = self.f.createVariable(fname, self._dtype, sdims)
            self.handles[fname].set_collective(True)

        self.handles[fname][step] = 0 # collectively create dataset
        self.handles[fname].set_collective(False)
        sf = tuple([step] + list(sf))
        sl = tuple(slices)
        if inside:
            self.handles[fname][sf] = field[sl]
        self.handles[fname].set_collective(True)
        self.f.sync()
