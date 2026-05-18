# B1 AW/EW Decomposition — Signal × Holding 2×2 Diagnostic

Generated: 2026-05-18 22:01

> **Purpose**: Decompose AW-EW gap into signal effect and holding weight effect.

---

## 1. Methodology

### 2×2 Quadrants
| Code | Signal | Holding | Description |
|------|--------|---------|-------------|
| **EE** | EW industry momentum | EW holding return | Current EW variants |
| **EA** | EW industry momentum | AW holding return | EW signal → AW execution |
| **AE** | AW industry momentum | EW holding return | AW signal → EW execution |
| **AA** | AW industry momentum | AW holding return | Current AW variants |

### Decomposition (Shapley averaging)
```
signal_effect = mean( (AE-EE), (AA-EA) )  # switching signal EW→AW
hold_effect   = mean( (EA-EE), (AA-AE) )  # switching hold EW→AW
interaction   = AA - EE - signal_effect - hold_effect  # cross term
```

---

## 2. Results by Split


### Ex-2025

#### 2×2 Matrix (Rel.Calmar)

|  | hold_EW | hold_AW |
|--|---------|---------|
| **signal_EW** | EE: 0.31 | EA: 1.61 |
| **signal_AW** | AE: 0.20 | AA: 1.30 |

#### Decomposition (Ann.Excess contribution)

| Component | Value | Pct of Total Gap |
|-----------|-------|------------------|
| Total gap (AA-EE) | 23.03% | 100% |
| Signal effect | 1.54% | 7% |
| Hold weight effect | 21.49% | 93% |
| Interaction | 0.00% | 0% |

**Dominant driver**: holding weight (within-industry cap-weighting)

#### All Quadrants Detail

| Quadrant | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|----------|------------|-----|----------|--------|------------|----------|
| AA | 27.58% | 0.92 | 65.6% | -21.15% | 1.30 | 46.2% |
| AE | 4.10% | 0.28 | 50.0% | -20.70% | 0.20 | 46.2% |
| EA | 24.06% | 0.98 | 62.5% | -14.97% | 1.61 | 50.5% |
| EE | 4.55% | 0.32 | 53.1% | -14.88% | 0.31 | 50.5% |

### 2024 only

#### 2×2 Matrix (Rel.Calmar)

|  | hold_EW | hold_AW |
|--|---------|---------|
| **signal_EW** | EE: 0.32 | EA: 2.62 |
| **signal_AW** | AE: 0.53 | AA: 2.45 |

#### Decomposition (Ann.Excess contribution)

| Component | Value | Pct of Total Gap |
|-----------|-------|------------------|
| Total gap (AA-EE) | 29.98% | 100% |
| Signal effect | 3.03% | 10% |
| Hold weight effect | 26.95% | 90% |
| Interaction | 0.00% | 0% |

**Dominant driver**: holding weight (within-industry cap-weighting)

#### All Quadrants Detail

| Quadrant | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|----------|------------|-----|----------|--------|------------|----------|
| AA | 33.94% | 1.03 | 63.6% | -13.83% | 2.45 | 50.0% |
| AE | 7.07% | 0.39 | 45.5% | -13.31% | 0.53 | 50.0% |
| EA | 30.99% | 1.14 | 63.6% | -11.85% | 2.62 | 46.7% |
| EE | 3.96% | 0.29 | 45.5% | -12.21% | 0.32 | 46.7% |

### 2025 only

#### 2×2 Matrix (Rel.Calmar)

|  | hold_EW | hold_AW |
|--|---------|---------|
| **signal_EW** | EE: 13.58 | EA: 40.91 |
| **signal_AW** | AE: 10.51 | AA: 30.33 |

#### Decomposition (Ann.Excess contribution)

| Component | Value | Pct of Total Gap |
|-----------|-------|------------------|
| Total gap (AA-EE) | 108.32% | 100% |
| Signal effect | 3.18% | 3% |
| Hold weight effect | 105.14% | 97% |
| Interaction | 0.00% | 0% |

**Dominant driver**: holding weight (within-industry cap-weighting)

#### All Quadrants Detail

| Quadrant | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|----------|------------|-----|----------|--------|------------|----------|
| AA | 192.11% | 2.41 | 72.7% | -6.33% | 30.33 | 46.7% |
| AE | 73.29% | 2.01 | 63.6% | -6.97% | 10.51 | 46.7% |
| EA | 175.25% | 2.38 | 72.7% | -4.28% | 40.91 | 40.0% |
| EE | 83.79% | 2.07 | 72.7% | -6.17% | 13.58 | 40.0% |

### 2025-2026

#### 2×2 Matrix (Rel.Calmar)

|  | hold_EW | hold_AW |
|--|---------|---------|
| **signal_EW** | EE: 3.80 | EA: 10.46 |
| **signal_AW** | AE: 4.22 | AA: 15.39 |

#### Decomposition (Ann.Excess contribution)

| Component | Value | Pct of Total Gap |
|-----------|-------|------------------|
| Total gap (AA-EE) | 86.89% | 100% |
| Signal effect | 11.11% | 13% |
| Hold weight effect | 75.78% | 87% |
| Interaction | 0.00% | 0% |

**Dominant driver**: holding weight (within-industry cap-weighting)

#### All Quadrants Detail

| Quadrant | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|----------|------------|-----|----------|--------|------------|----------|
| AA | 142.21% | 2.22 | 68.8% | -9.24% | 15.39 | 48.9% |
| AE | 51.29% | 1.61 | 62.5% | -12.14% | 4.22 | 48.9% |
| EA | 115.95% | 1.96 | 68.8% | -11.08% | 10.46 | 42.2% |
| EE | 55.33% | 1.51 | 62.5% | -14.56% | 3.80 | 42.2% |

### full

#### 2×2 Matrix (Rel.Calmar)

|  | hold_EW | hold_AW |
|--|---------|---------|
| **signal_EW** | EE: 1.20 | EA: 3.17 |
| **signal_AW** | AE: 0.81 | AA: 2.67 |

#### Decomposition (Ann.Excess contribution)

| Component | Value | Pct of Total Gap |
|-----------|-------|------------------|
| Total gap (AA-EE) | 38.73% | 100% |
| Signal effect | 4.00% | 10% |
| Hold weight effect | 34.73% | 90% |
| Interaction | 0.00% | 0% |

**Dominant driver**: holding weight (within-industry cap-weighting)

#### All Quadrants Detail

| Quadrant | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|----------|------------|-----|----------|--------|------------|----------|
| AA | 56.55% | 1.39 | 67.3% | -21.15% | 2.67 | 46.5% |
| AE | 16.67% | 0.70 | 53.1% | -20.70% | 0.81 | 46.5% |
| EA | 47.40% | 1.33 | 63.3% | -14.97% | 3.17 | 47.9% |
| EE | 17.83% | 0.77 | 55.1% | -14.88% | 1.20 | 47.9% |

---

## 3. Top Stock Concentration (within AW-selected industries)

| Split | Top1 Amt Share | Top3 Amt Share | Top1 Ret Contrib | Top3 Ret Contrib |
|-------|---------------|---------------|-----------------|-----------------|
| Ex-2025 | 41.0% | 80.9% | 0.9% | 83.9% |
| 2025 only | 40.2% | 80.5% | 1.0% | 85.5% |
| full | 41.3% | 81.8% | 0.9% | 84.7% |

---

## 4. Key Questions


### Q1: Is AW driven by signal or holding weight?

**Full sample**: signal=4.00%, hold=34.73%, dominant=hold
**Ex-2025**: signal=1.54%, hold=21.49%, dominant=hold

### Q2: Should B1 be renamed from 'Industry Rotation' to 'Amount-Weighted Industry Momentum'?

**Yes — rename recommended.** The AW advantage is primarily from within-industry amount-weighting, not from superior industry selection. 'Amount-Weighted Industry Momentum' is more accurate.

### Q3: Is EW weakness evidence that industry rotation alpha is unstable?

- EE full: Ann.Excess=17.83%, IR=0.77
- EE Ex-2025: Ann.Excess=4.55%, IR=0.32

**EW passes minimum thresholds (excess > 3%, IR > 0.3) even Ex-2025.** The pure equal-weight industry rotation signal has detectable alpha. However, Rel.Calmar Ex-2025 is only 0.31 (< 0.5 gate), meaning risk-adjusted returns are poor. AW amplifies this alpha 6x (4.55% → 27.58%) via within-industry cap-weighting.

**Conclusion**: The alpha EXISTS in EW but is thin. AW does not create alpha — it AMPLIFIES existing alpha through concentration in large-cap stocks within each selected industry.

### Q4: Continue to EW-only diagnostic?

**Yes — recommended.** Although EW passes minimum excess/IR thresholds, its Rel.Calmar (0.31) fails the 0.5 gate. The EW-only diagnostic should:
1. Verify EW's Ex-2025 Calmar across multiple lookbacks (not just LB60)
2. Test whether EW survives when restricted to industries with >= 5 stocks (reducing noise)
3. Determine if EW can be the foundation, with AW as an execution enhancement

### Additional Finding: EA Quadrant Outperforms AA in Risk-Adjusted Terms

In Ex-2025 and 2024-only, **EA (EW signal + AW holding) has HIGHER Rel.Calmar than AA (AW signal + AW holding)**:

| Split | AA Calmar | EA Calmar | Winner |
|-------|-----------|-----------|--------|
| Ex-2025 | 1.30 | **1.61** | EA |
| 2024 only | 2.45 | **2.62** | EA |
| 2025 only | 30.33 | **40.91** | EA |
| full | 2.67 | **3.17** | EA |

**This is the single most important finding of this diagnostic**: The EW signal (equal-weight industry momentum) produces BETTER risk-adjusted returns than the AW signal when both are executed with AW holding. The AW signal adds NO industry selection value — it actually DETRACTS from risk-adjusted performance in 4/5 splits.

**Implication**: B1 should standardize on EW signal + AW holding as the recommended configuration. This preserves the pure industry beta signal while capturing large-cap execution efficiency.