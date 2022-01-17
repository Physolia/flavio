"""Functions for parsing the parameter data files"""

import yaml
import pkgutil
from flavio.classes import *
from flavio.statistics.probability import *
from flavio._parse_errors import errors_from_string
import flavio
import re
from flavio.measurements import _fix_correlation_matrix
from math import sqrt
from particle import Particle, data as p_data


def _read_yaml_object_metadata(obj, constraints):
    parameters = yaml.safe_load(obj)
    for parameter_name, info in parameters.items():
        p = Parameter(parameter_name)
        if 'description' in info and info['description'] is not None:
            p.description = info['description']
        if 'tex' in info and info['tex'] is not None:
            p.tex = info['tex']

def read_file_metadata(filename, constraints):
    """Read parameter values from a YAML file."""
    with open(filename, 'r') as f:
        _read_yaml_object_metadata(f, constraints)

def _read_yaml_object_values(obj, constraints):
    parameters = yaml.safe_load(obj)
    for parameter_name, value in parameters.items():
        p = Parameter[parameter_name] # this will raise an error if the parameter doesn't exist!
        constraints.set_constraint(parameter_name, value)

def _read_yaml_object_new(obj):
    """Read parameter constraints from a YAML stream or file that are compatible
    with the format generated by the `get_yaml` method of
    `flavio.classes.ParameterConstraints`."""
    parameters = yaml.safe_load(obj)
    return ParameterConstraints.from_yaml_dict(parameters)

def _read_yaml_object_values_correlated(obj, constraints):
    list_ = yaml.safe_load(obj)
    for parameter_group in list_:
        parameter_names = []
        central_values = []
        errors = []
        for dict_list in parameter_group['values']:
            parameter_name, value = list(dict_list.items())[0]
            Parameter[parameter_name] # this will raise an error if the parameter doesn't exist!
            parameter_names.append(parameter_name)
            error_dict = errors_from_string(value)
            central_values.append(error_dict['central_value'])
            squared_error = 0.
            for sym_err in error_dict['symmetric_errors']:
                squared_error += sym_err**2
            for asym_err in error_dict['asymmetric_errors']:
                squared_error += asym_err[0]*asym_err[1]
            errors.append(sqrt(squared_error))
        correlation = _fix_correlation_matrix(parameter_group['correlation'], len(parameter_names))
        covariance = np.outer(np.asarray(errors), np.asarray(errors))*correlation
        if not np.all(np.linalg.eigvals(covariance) > 0):
            # if the covariance matrix is not positive definite, try a dirty trick:
            # multiply all the correlations by 0.99.
            n_dim = len(correlation)
            correlation = (correlation - np.eye(n_dim))*0.99 + np.eye(n_dim)
            covariance = np.outer(np.asarray(errors), np.asarray(errors))*correlation
            # if it still isn't positive definite, give up.
            assert np.all(np.linalg.eigvals(covariance) > 0), "The covariance matrix is not positive definite!" + str(covariance)
        constraints.add_constraint(parameter_names, MultivariateNormalDistribution(central_values, covariance))

def read_file(filename):
    """Read parameter values from a YAML file in the format generated by the
    `get_yaml` method of the `ParameterConstraints` class, returning a
    `ParameterConstraints` instance."""
    with open(filename, 'r') as f:
        return _read_yaml_object_new(f)

def read_file_values(filename, constraints):
    """Read parameter values from a YAML file."""
    with open(filename, 'r') as f:
        _read_yaml_object_values(f, constraints)

def read_file_values_correlated(filename, constraints):
    """Read parameter values from a YAML file."""
    with open(filename, 'r') as f:
        _read_yaml_object_values_correlated(f, constraints)

def write_file(filename, constraints):
    """Write parameter constraints to a YAML file."""
    with open(filename, 'w') as f:
        yaml.dump(constraints.get_yaml_dict(), f)

class FlavioParticle(Particle):
    """This class extends the `particle.Particle` class.

    Additional class methods
    ------------------------
    - from_flavio_name(flavio_name)
      returns a class instance for a given `flavio_name`
    - flavio_all()
      returns a set of all class instances used in flavio

    Additional properties
    ---------------------
    - flavio_name
      the particle name as used in flavio if defined, otherwise `None`
    - latex_name_simplified
      a simplified version of the latex name returned by `latex_name`
    - flavio_m
      a tuple with data on the particle mass as used in flavio, containing
      entries `name`, `tex`, `description`, `central`, `right`, `left`
    - flavio_tau
      a tuple with data on the particle lifetime as used in flavio, containing
      entries `name`, `tex`, `description`, `central`, `right`, `left`
    """

    PDG_PARTICLES = {
        'Bs': 531,
        'Bc': 541,
        'Bs*': 533,
        'B*+': 523,
        'B*0': 513,
        'B+': 521,
        'B0': 511,
        'Ds': 431,
        'Ds*': 433,
        'D+': 411,
        'D0': 421,
        'h': 25,
        'J/psi': 443,
        'KL': 130,
        'KS': 310,
        'K*+': 323,
        'K*0': 313,
        'K+': 321,
        'K0': 311,
        'Lambda': 3122,
        'Lambdab': 5122,
        'Lambdac': 4122,
        'omega': 223,
        'D*0': 423,
        'D*+': 413,
        'W': 24,
        'Z': 23,
        'e': 11,
        'eta': 221,
        'f0': 9010221,
        'mu': 13,
        'phi': 333,
        'pi+': 211,
        'pi0': 111,
        'psi(2S)': 100443,
        'rho+': 213,
        'rho0': 113,
        't': 6,
        'tau': 15,
        'u': 2,
        'p': 2212,
        'n': 2112,
    }
    _pdg_particles_inv = {v:k for k,v in PDG_PARTICLES.items()}
    _pdg_tex_regex = re.compile(
        r"^([A-Za-z\\/]+)" # latin or greek letters or slash
        r"(?:_\{(.*?)\})*" # _{...}
        r"(?:\^\{(.*?)\})*" # ^{...}
        r"(?:\((.*?)\))*" # (...)
        r"(?:\^\{(.*?)\})*" # ^{...}
    )

    @classmethod
    def from_flavio_name(cls, flavio_name):
        return cls.from_pdgid(cls.PDG_PARTICLES[flavio_name])

    @classmethod
    def flavio_all(cls):
        return {particle for particle in cls.all() if particle.flavio_name}

    @property
    def flavio_name(self):
        return self._pdg_particles_inv.get(self.pdgid, None)

    @property
    def latex_name_simplified(self):
        m = self._pdg_tex_regex.match(self.latex_name)
        if m is None:
            return self.latex_name
        name = m.group(1)
        sub = m.group(2)
        sup = (m.group(3) or '') + (m.group(5) or '')
        par = m.group(4)
        if sub or name in ('W', 'Z', 'H', 'e', '\\mu', '\\tau'):
            # remove superscripts +-0 and keep only *
            sup = '*' if '*' in sup else ''
        if not sub and par and not par.isdigit() and name != 'J/\\psi':
            # subscript absent and parantheses contain letter but not for 'J/\\psi'
            sub = par
        sub_tex = r'_{' + sub + r'}' if sub else ''
        sup_tex = r'^{' + sup + r'}' if sup else ''
        return name + sub_tex + sup_tex

    @property
    def flavio_m(self):
        name = 'm_' + self.flavio_name
        tex = r'$m_{' + self.latex_name_simplified + '}$'
        pole_mass = ' quark pole' if self.name == 't' else ''
        description = r'${}${} mass'.format(
            self.latex_name_simplified, pole_mass
        )
        central = self.mass*1e-3
        right = self.mass_upper*1e-3
        left = self.mass_lower*1e-3
        return name, tex, description, central, right, left

    @property
    def flavio_tau(self):
        if {self.width, self.width_upper, self.width_lower} & {None, 0}:
            return None
        name = 'tau_' + self.flavio_name
        tex = r'$\tau_{' + self.latex_name_simplified + '}$'
        description = r'${}$ lifetime'.format(self.latex_name_simplified)
        G_central = self.width*1e-3
        G_right = self.width_upper*1e-3
        G_left = self.width_lower*1e-3
        central = 1/G_central # life time = 1/width
        right = G_right/G_central**2
        left = G_left/G_central**2
        return name, tex, description, central, right, left

def read_pdg(year, constraints):
    """Read particle masses and widths from the PDG data file of a given year."""
    FlavioParticle.load_table(p_data.basepath / f"particle{year}.csv")
    for particle in FlavioParticle.flavio_all():
        for data in (particle.flavio_m, particle.flavio_tau):
            if data is None:
                continue
            name, tex, description, central, right, left = data
            try:
                # if parameter already exists, remove existing constraints on it
                p = Parameter[name]
                constraints.remove_constraint(name)
            except KeyError:
                # otherwise, create it
                p = Parameter(name)
            p.tex = tex
            p.description = description
            if right == left:
                constraints.add_constraint([name],
                    NormalDistribution(central, right))
            else:
                constraints.add_constraint([name],
                    AsymmetricNormalDistribution(central,
                    right_deviation=right, left_deviation=left))



############### Read default parameters ###################

# Create the object
default_parameters = ParameterConstraints()

# read default parameters
default_parameters.read_default()
