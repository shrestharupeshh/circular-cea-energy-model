"""crop.py - transpiration: how the crop moves water into the air."""

import numpy as np
from src.constants import LAMBDA
from src.psychro import vpd

def transpiration(R_net, T_air, RH, LAI, a=0.30, b=0.010):
    """Simplified ratiation + VPD driven transpiration.
    Returns kg water per m2 floor area per second.
    R_net : net radiation absorbed by canopy [W/m2]
    a,b : calibration coefficients - document them as assumptions."""

    D = vpd(T_air, RH)                     # Pa
    latent_flux = a * R_net + b * LAI * D  # W/m2
    return np.maximum(latent_flux, 0.0) / LAMBDA  # kg/m2/s
