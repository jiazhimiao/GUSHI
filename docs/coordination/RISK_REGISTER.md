# RISK_REGISTER

| Risk | Severity | Status | Mitigation |
|---|---:|---|---|
| Overfitting weak alpha | High | Active | Offline gates, year split, costs |
| Future leakage | High | Active | T+1 open, point-in-time checks |
| Token leakage | High | Active | .env gitignored, grep before commit |
| Historical constituents bias | Medium | Active | Do not use for event trading |
| Industry classification hindsight | Medium | Active | Disclose in B1, sensitivity checks |
| Git push blocked | Low | Active | Local bundle backup |
| Paper trading too early | High | Controlled | Explicitly prohibited until strategy passes |
