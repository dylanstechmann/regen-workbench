# Force–displacement fixture qualification protocol

## Purpose and boundary

This protocol qualifies the measurement chain for direct tooth mobility before
any biological comparison. It covers the force channel, displacement channel,
load frame, fixture, contact tip, data acquisition clock, and analysis pipeline.
It is a bench metrology plan, not a tooth-loading protocol, trauma model,
patient-care instruction, or evidence that a regeneration strategy works.

The target quantity is tooth displacement relative to a stable fixture frame
under a measured force at the specimen contact. The actuator command is not a
substitute for either quantity. For the displacement channel, the observed
signal can contain tooth movement, frame/fixture compliance, sensor drift,
registration error, and contact slip. Each contribution needs an independent
check before a tooth–PDL response is interpreted.

## Why rate and timing are part of calibration

A primary device-development study separately applied crown displacement,
measured force with an integrated sensor, and measured displacement with a
magnetic sensor array. Its in-vitro work used four porcine mandibular segments;
the in-vivo demonstration included two volunteers. Force progression changed
with activation velocity. A later in-vivo study of five healthy volunteers
applied a 0–0.15 mm crown deflection over loading times from 0.1 to 5 seconds
and also found force depended on loading time. These small studies support
controlling and recording the waveform and timing; they do not define a trauma
loading range, a target response, or a universal acceptance limit.
[Drolshagen et al., 2011](https://pubmed.ncbi.nlm.nih.gov/21679952/);
[Keilig et al., 2016](https://pubmed.ncbi.nlm.nih.gov/26395824/).

## Lock the measurement contract before calibration

Record and freeze the following for each instrument configuration:

- Force and displacement sensor make, model, serial number, range, resolution,
  mounting, calibration identifier, and reference-standard certificate.
- Contact geometry and contact point; signed loading axis; lever arms; specimen
  and fixture coordinate frames; direction and sign conventions.
- Whether the actuator is displacement-controlled or force-controlled, the
  command waveform, sampling rate, filters, trigger source, and time origin.
- Planned force/displacement operating ranges and loading rates for the future
  assay. Select these from the validated apparatus and protocol question; do
  not copy a human orthodontic or animal injury value as a new injury dose.
- The smallest displacement change the future study needs to distinguish,
  denoted `delta_min`, and the pre-outcome-review limits for bias, repeatability,
  fixture residual, drift, and channel timing. The research team must choose
  the numeric limits before seeing comparative outcomes.

Use the same physical configuration and analysis pipeline for all traces in a
single analysis run. If a sensor, calibration, filter, axis transform, fixture,
or correction model changes, issue a new calibration or pipeline identifier.

## Bench sequence

| Gate | Bench check | Record | Advance only when |
|---|---|---|---|
| 1. Force channel | Compare the installed force sensor with an independently calibrated reference over the intended range, including ascending and descending points and zero return. Repeat before and after a session. | Reference force, indicated force, direction, time/rate, point, repeat, uncertainty, temperature, instrument IDs, and calibration certificate. | Bias, hysteresis, zero return, drift, and uncertainty meet criteria frozen for the intended range. |
| 2. Displacement channel | Move a rigid target through independently known stage positions in each intended axis and direction. Include zero-motion repeats and return-to-zero checks. | Reference position, indicated position, direction, point, repeat, uncertainty, stage and sensor IDs, and calibration certificate. | Axis sign, linearity or declared nonlinear mapping, bias, repeatability, and drift meet frozen criteria. |
| 3. Frame and fixture compliance | Replace the tooth-like specimen with a rigid load-path block or bypass that sends load into the frame without a compliant specimen. Repeat the planned direction and rate conditions. | Applied force and apparent relative displacement throughout loading, unloading, and recovery, plus fixture state and contact location. | Apparent displacement and hysteresis are quantified; residual uncertainty after any proposed correction is below the predeclared limit. |
| 4. Time alignment | Send one shared trigger or calibration event to force and displacement acquisition channels. Estimate channel offset and jitter at the fastest planned waveform. | Trigger source, timestamps, offset, jitter, sampling rates, and synchronization method. | The maximum displacement error from timing uncertainty, `v_max × delta_t`, is below the timing-error budget allocated from `delta_min`. |
| 5. Integrated known-motion check | Run the complete fixture, sensors, acquisition, and analysis chain on a rigid phantom moved through blinded, known translations and rotations, including zero motion. | Phantom truth, measured pose, force trace, displacement trace, run code, operator, session, and frozen pipeline. | The position pipeline and force/displacement channels each meet their own criteria; one passing channel cannot mask another failing channel. |
| 6. Repeatability and drift | Re-seat and re-run coded phantom states across operators or sessions included in the intended study. Randomize state order; preserve zero-motion controls and all failed runs. | Independent reseating status, run code, operator/session, order, calibration IDs, environmental conditions, and failure reason. | Bias and repeatability uncertainty are bounded tightly enough for the locked `delta_min`; otherwise revise the apparatus and repeat qualification. |

Do not assume fixture compliance is constant. Describe it over the measured
force, direction, time, and rate range. If a correction is required, preserve
raw and corrected signals, define the correction function and version, and
validate it on held-out known-force and known-motion states. Do not extrapolate
outside the qualified range. A correction fit to the same traces used to claim
successful qualification is not independent validation.

## Acceptance logic and stop rules

There is no published trauma-restoration calibration threshold to import. Set
study-specific limits before outcome review. At minimum, the criteria record
should define:

- maximum force-channel bias and uncertainty over the intended range;
- maximum displacement-channel bias, repeatability, and zero-return error;
- maximum blocked-fixture apparent movement and residual after correction;
- maximum force/displacement timestamp offset and jitter;
- maximum pre/post-session calibration drift; and
- the decision rule connecting these uncertainties to `delta_min`.

The existing position analyzer requires frozen component-wise pose criteria;
the mobility-response analyzer intentionally reports descriptive values only.
Neither can establish that a real instrument has passed this protocol. If a
gate fails, do not analyze biological differences as if the failed channel
were qualified. Correct the hardware or pipeline, assign a new version, and
repeat the affected gates. Keep failed and unmeasurable runs in the disposition
record.

## Required records and connection to the analysis tools

Keep calibration-point records separate from specimen response traces. Each
calibration record should identify the reference device and certificate,
calibration date, operator, environment, instrument configuration, axis,
direction, rate, reference value, indicated value, repeat number, uncertainty,
and any correction model. Store the raw time series and a checksum for each
source file. Calibration identifiers in
[`mobility_response_data_dictionary.tsv`](mobility_response_data_dictionary.tsv)
must resolve to these records.

After qualification, the
[`analyze_mobility_response.py`](analyze_mobility_response.py) script can
summarize traces using the frozen calibration and pipeline identifiers. Its
signed force–displacement path integral is descriptive; interpret it as a
closed-cycle hysteresis quantity only when the full cycle closes, channels are
aligned, sign conventions are verified, and fixture artifacts have been
qualified. Keep sensor calibration results, fixture corrections, tooth pose,
and tissue identity as separate outputs.

The first physical implementation should stop at rigid and independently
characterized mechanical phantoms. Any later ex-vivo, animal, or human work
needs its own reviewed protocol, sample-handling controls, and appropriate
institutional approvals. This document does not authorize that work.

## Sources

- Drolshagen M, et al. *Development of a novel intraoral measurement device to determine the biomechanical characteristics of the human periodontal ligament.* Journal of Biomechanics. 2011. [PubMed](https://pubmed.ncbi.nlm.nih.gov/21679952/) · [DOI](https://doi.org/10.1016/j.jbiomech.2011.05.025).
- Keilig L, et al. *In vivo measurements and numerical analysis of the biomechanical characteristics of the human periodontal ligament.* Annals of Anatomy. 2016. [PubMed](https://pubmed.ncbi.nlm.nih.gov/26395824/) · [DOI](https://doi.org/10.1016/j.aanat.2015.08.004).
