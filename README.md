![Gateway Deployment](https://github.com/biosimulators/compose-server/actions/workflows/deploy-gateway.yml/badge.svg)
![Worker Deployment](https://github.com/biosimulators/compose-server/actions/workflows/deploy-worker.yml/badge.svg)

# BioCompose Server

## *FOR DEVS*:

### _Generate gRPC service stubs:_
```bash
python shared/parse_proto.py
```

### _Generate OpenAPI spec yml:_
```bash
python client/openapi_spec.py
```

### _Apply overlay changes_:
```bash
cd kustomize \
  && kubectl kustomize overlays/compose | kubectl apply -f - \
  && cd ..
```