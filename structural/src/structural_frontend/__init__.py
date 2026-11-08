"""Sound shortcuts for unrestricted graphical population-memory horizons.

The front end never infers a finite horizon from acyclicity. Its outputs
classify graph-based queries; numerical parameter points are checked separately.
"""
from .precheck import precheck, early_self_loop_certificates
from .certificate_checker import check_certificate, explain_certificate

__all__ = ["precheck", "early_self_loop_certificates", "check_certificate",
           "explain_certificate"]
