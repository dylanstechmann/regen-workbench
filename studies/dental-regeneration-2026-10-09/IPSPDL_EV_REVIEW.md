# iPSC-derived PDL extracellular-vesicle evidence review

This review adds Taniguchi et al. (2026), an open-access comparison of EVs
released by iPSC-derived PDL-like cells (iPS-PDL-EVs) and primary PDL cells
(PDL-EVs). The article PDF and hash-linked Regen provenance are recorded in
[ipspdl_ev_receipt.json](ipspdl_ev_receipt.json). The paper is CC BY 4.0; this
file paraphrases its results.

## Evidence update

The evidence now spans two distinct questions. Wu et al. (2025) report in the
PubMed abstract that transplanted human iPS-PDL cells increased new-bone height
and periodontal-tissue regeneration in a rat defect model at four weeks. The
abstract does not give the animal or defect denominator, exact iPSC line, group
allocation, or mechanical function result. The publisher full text was not
available in the retrieved record, so this is an abstract-limited orthotopic
signal, not a quantified estimate or evidence of load-bearing attachment.

Taniguchi et al. (2026) isolate EVs from three independently differentiated
iPS-PDL batches and compare them with EVs from primary PDL-cell batches. The
paper identifies the iPSC and primary PDL sources as established commercial
cell lines, but does not state a parental iPSC line identifier or map the
differentiated batches to independent iPSC donors. It reports particle and
vesicle characterization, uptake into PDL cells, and in-vitro effects. Using
the tested protein-normalized preparations, iPS-PDL-EVs increased the WST-8
proliferation readout at 48 and 72 hours at all tested concentrations. Both
EV sources increased Transwell migration counts after 24 hours; the iPS-PDL-EV
group exceeded the primary PDL-EV group at 0.5 and 1.0 µg/mL, but not at
0.25 µg/mL. The experiments were independently repeated three times with
biological replicates.

The miRNA analysis detected 500 species in iPS-PDL-EVs and 479 in PDL-EVs,
with 433 shared. Three candidates (miR-181a-2-3p, let-7i-5p and let-7g-5p) were
higher in iPS-PDL-EVs. Transfected mimics lowered IL1R1 or FAS expression and
increased proliferation and migration readouts in recipient PDL cells. This
supports candidate-miRNA sufficiency in the mimic assay. It does not show that
those RNAs are necessary for the complete EV effect: the study did not report
depletion/blockade of the candidates inside EVs followed by rescue. MAPK/Akt
activation by the EV preparation is observed, while the full causal chain from
EV cargo to signaling to tissue repair remains a hypothesis.

## Interpretation and limits

The 2025 cell-transplant report supplies an early orthotopic animal bridge for
the iPS-PDL cell source. The 2026 EV study adds a plausible paracrine
mechanism and a cell-free research branch, but it tested cultured human PDL
cells only. It did not test EVs in a periodontal defect, at a tooth root, or
under physiological loading. This is not independent replication of the 2025
cell-transplant result; the studies share investigators and the later paper
uses the earlier cell-differentiation method.

Several features limit interpretation of the EV comparison. Doses were set by
total EV-preparation protein measured with BCA, not matched particle counts,
so greater activity per particle is not established. The migration assay
counts cells after a 24-hour exposure, while the same EV preparations also
increase a proliferation-associated readout; the methods do not describe a
proliferation-blocking control, so migration and cell division may contribute
to the count. The study itself identifies the lack of animal efficacy,
biodistribution and longer-term safety data. It reports no cementum/PDL/bone
insertion, periodontal-space preservation, ankylosis or resorption assessment,
tooth mobility, or load transfer for the EV intervention.

The earlier Li et al. (2026) cell-function study remains relevant: it uses one
named iPSC line (HPS0381), three conditioned-medium batches and reports that
one batch resembles dermal fibroblasts for several markers. The EV paper's
three independently differentiated batches should not be treated as proof of
independent parental iPSC donor replication without a line-to-batch map.

## Most discriminating next evidence

The focused hypothesis is that iPS-PDL-EVs can recruit or support host PDL
cells through paracrine signaling, while a local cell-free intervention may
avoid some issues specific to grafted pluripotent-cell-derived products. That
is a testable idea, not a demonstrated advantage. It would be weakened if the
EV advantage disappeared under particle-matched comparisons, if the migration
effect disappeared after separating it from proliferation, or if a tooth-site
study showed bone formation without oriented insertion and preserved ligament
space.

The next useful comparisons are independent parental iPSC lines and PDL donors;
particle-count and protein-normalized EV comparisons; a test of whether
candidate miRNA depletion removes the EV effect; and an orthotopic defect study
that measures oriented insertion at both interfaces, ligament-space width,
ankylosis, root resorption, mobility, mechanical response and durability. The
cell transplant and EV arms should remain separate. These are evidence
requirements, not a laboratory protocol or a clinical recommendation.

The underlying-cell RNA-seq data cited by the 2026 EV paper are in DDBJ BioProject
PRJDB39888 (runs DRR913328–DRR913336). That archive is a potential next
computational audit of parent-cell identity and expression contrasts; no raw
reads or derived expression estimates are analyzed in this review.
