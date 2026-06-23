# Barrett-Kok State Model

This page documents the analytical Barrett-Kok state used by the
`qsavory_exact` simulator series. It is the theoretical source for the exact
raw elementary-pair density matrix and for the raw fidelity used to instantiate
the Werner approximation.

## Optical Parameters

For an elementary link of length \(L\), the midpoint Bell-state measurement
station is placed halfway between the two end nodes. A photon emitted by either
memory therefore travels a half-link optical arm of length \(L/2\).

Let:

- \(\alpha\) be the fiber attenuation in dB/km;
- \(\eta_{\mathrm{emit}}\) be the memory emission efficiency;
- \(\eta_{\mathrm{coll}}\) be the collection efficiency into the optical mode;
- \(\eta_{\mathrm{conv}}\) be the frequency-conversion efficiency;
- \(\eta_d\) be the detector efficiency;
- \(p_d\) be the excess detector dark-click probability per modeled detection
  opportunity;
- \(\mathcal{V}\) be the mode-matching visibility;
- \(m\in\{0,1\}\) be the click-pattern parity bit.

The half-link fiber transmissivity is

\[
T_{\mathrm{fiber}} = 10^{-\alpha L/20}.
\]

The source-side transmissivity before fiber loss is

\[
\eta_{\mathrm{source}}
    = \eta_{\mathrm{emit}}\eta_{\mathrm{coll}}\eta_{\mathrm{conv}}.
\]

The total transmissivity from a memory to the midpoint BSM input is

\[
\eta
    = \eta_{\mathrm{source}}T_{\mathrm{fiber}}
    = \eta_{\mathrm{emit}}\eta_{\mathrm{coll}}\eta_{\mathrm{conv}}
      T_{\mathrm{fiber}}.
\]

For the symmetric three-node comparison, both arms use the same value:

\[
\eta^A = \eta^B = \eta.
\]

The probability of a signal-induced detector click on one arm is

\[
p_{\mathrm{signal}} = \eta\eta_d.
\]

Including dark clicks while avoiding double-counting the event in which both a
signal click and a dark click occur in the same detector window gives

\[
p_{\mathrm{click}}
    = p_{\mathrm{signal}} + p_d - p_{\mathrm{signal}}p_d .
\]

The shared elementary success-probability model is

\[
p_{\mathrm{BK}} = \frac{1}{2}p_{\mathrm{click}}^2.
\]

This success probability controls the stochastic generation process. The
density matrix below controls the state assigned after a successful generation
event.

## Exact Barrett-Kok Density Matrix

QuantumSavory's `BarrettKokBellPair` state follows the analytical state model
implemented in `StatesZoo`. The state is parameterized by
\(\eta^A,\eta^B,p_d,\eta_d,\mathcal{V}\), and \(m\).

Define

\[
d_1^{(0)} = d_2^{(0)}
    = \frac{\eta^A\eta^B\eta_d^2}{4},
\]

\[
d_3^{(0)}
    = d_1^{(0)}|\mathcal{V}|^2(-1)^m,
\]

\[
d_1^{(1)}
    = (1-p_d)\eta_d(\eta^A+\eta^B-2\eta^A\eta^B\eta_d)
      + p_d(1-\eta^A\eta_d)(1-\eta^B\eta_d),
\]

and the normalization

\[
N_d
    = 2(1-p_d)^4d_1^{(0)}
      + 4p_d(1-p_d)^2d_1^{(1)}.
\]

The single-excitation contribution is

\[
\begin{aligned}
A
    &= d_1^{(0)}
       \left(
           |01\rangle\!\langle 01|
           + |10\rangle\!\langle 10|
       \right) \\
    &\quad
       + d_3^{(0)}
       \left(
           |01\rangle\!\langle 10|
           + |10\rangle\!\langle 01|
       \right).
\end{aligned}
\]

The dark-count mixed contribution is

\[
B = d_1^{(1)} I\otimes I.
\]

The normalized exact raw state is therefore

\[
\rho_{\mathrm{BK}}
    =
    \frac{(1-p_d)^4 A + p_d(1-p_d)^2 B}{N_d}.
\]

This is not, in general, a Werner state. It preserves the structure of the
Barrett-Kok optical process through the relative weights of the
single-excitation sector, the visibility-dependent coherence term, and the
dark-count contribution.

## Raw Fidelity

The Bell-state fidelity used by the shared configuration is the overlap of
\(\rho_{\mathrm{BK}}\) with the target Bell state. In the symmetric case used
by the comparison, this reduces to

\[
F_{\mathrm{raw}}
    =
    \frac{
        (1-p_d)^4\left(d_1^{(0)}+d_3^{(0)}\right)
        + p_d(1-p_d)^2d_1^{(1)}
    }{
        2(1-p_d)^4d_1^{(0)}
        + 4p_d(1-p_d)^2d_1^{(1)}
    }.
\]

This value is stored in the resolved shared configuration as
`derived.barrett_kok_raw_fidelity`.

## Werner Approximation

The `qsavory_werner` simulator series replaces the exact Barrett-Kok density
matrix by a depolarized Bell pair with the same raw fidelity. QuantumSavory's
`DepolarizedBellPair` represents

\[
\rho_W
    =
    p|\Phi^+\rangle\!\langle\Phi^+|
    + (1-p)\frac{I}{4},
\qquad
|\Phi^+\rangle
    =
    \frac{|00\rangle+|11\rangle}{\sqrt{2}}.
\]

The Werner parameter \(p\) and fidelity \(F\) satisfy

\[
F = \frac{3p+1}{4},
\qquad
p = \frac{4F-1}{3}.
\]

In this comparison we set

\[
F = F_{\mathrm{raw}}.
\]

The Werner approximation is included for two reasons. First, Werner states are
a common approximation in quantum-network modeling. Second, SeQUeNCe is run
with a Bell-diagonal-state representation, which is the natural representation
for this comparison and is analogous to the Werner abstraction used by
`DepolarizedBellPair`. Running QuantumSavory with both `BarrettKokBellPair` and
`DepolarizedBellPair` separates protocol-level agreement from the effect of the
chosen quantum-state representation.
