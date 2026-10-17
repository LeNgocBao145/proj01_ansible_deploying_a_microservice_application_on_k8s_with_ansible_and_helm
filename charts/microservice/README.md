# Vendored microservice chart

This chart is based on version 0.1.0 of the upstream chart at
https://github.com/iankisali/microservice-deployment/tree/main/chart/microservice.
The upstream clone under `/opt/microservice-deployment` remains unchanged and
continues to supply the per-service values files. This vendored copy adds
optional Kubernetes liveness/readiness probes and resource requests/limits.

The chart version is 0.2.0 to distinguish the local extension from upstream.
Resource profiles are generated from live `kubectl top pods --containers`
samples by `playbooks/measure-resources.yml`; no resource quantities are
hard-coded before a measurement run.
