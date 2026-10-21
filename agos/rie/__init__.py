"""RIE — Repository Intelligence Engine (platform package ``agos.rie``).

Layers: ``contracts`` (data contracts), ``domain`` (repository model), ``detectors``
(feature detectors), ``application`` (pipeline, scoring, DNA generation),
``infrastructure`` (git fetch, filesystem), ``adapters`` (entry points).

R-F-006: this file makes ``rie`` a regular package (it was an implicit namespace
package) and all intra-package imports are relative, so it imports identically as
``rie`` (with ``agos/`` on ``sys.path``) and as ``agos.rie``. Its relationship to the
kernel's repository analysis is consolidated in R-W2-006.
"""
