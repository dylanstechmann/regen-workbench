#!/usr/bin/env bash
set -euo pipefail

DATA=/data
REVIEW=/work
FASTQ="$DATA/literature/ddbj-ipspdl-rnaseq-PRJDB39888/fastq"
INDEX="$DATA/structures/ipspdl-rnaseq/gencode-v50-transcripts-only"
QC="$DATA/structures/ipspdl-rnaseq/fastqc"
QUANT="$DATA/structures/ipspdl-rnaseq/quant"
TMP_READS="$DATA/structures/ipspdl-rnaseq/gzip-inputs"
THREADS="${THREADS:-8}"

mkdir -p "$QC" "$QUANT" "$TMP_READS"
test -s "$INDEX/index.ssi" || { echo "Missing Salmon index: $INDEX" >&2; exit 2; }
{
    salmon --version
    fastqc --version
    multiqc --version
} > "$DATA/structures/ipspdl-rnaseq/tool_versions.txt" 2>&1

printf 'file\tstatus\n' > "$QC/fastqc_status.tsv"
# Convert once: Salmon needs seekable FASTQ files, and FastQC's BZip2 handler
# did not handle this archive consistently. Reuse the local gzip files for QC
# and quantification.
export TMP_READS
find "$FASTQ" -maxdepth 1 -type f -name '*.fastq.bz2' -print0 |
    xargs -0 -n 1 -P 4 bash -c '
        set -euo pipefail
        source_file=$1
        name=$(basename "$source_file")
        output="$TMP_READS/${name%.bz2}.gz"
        if [[ ! -s "$output" ]]; then
            partial="${output}.part"
            bzip2 -dc "$source_file" | gzip -1 > "$partial"
            mv "$partial" "$output"
        fi
    ' _

gzip_reads=("$TMP_READS"/*.fastq.gz)
fastqc --quiet --noextract --threads 6 --outdir "$QC" "${gzip_reads[@]}" > "$QC/fastqc.log" 2>&1 || true
for file in "${gzip_reads[@]}"; do
    name=$(basename "$file" .gz)
    report="$QC/${name%.fastq}_fastqc.html"
    if [[ -s "$report" ]]; then
        printf '%s\treport_generated\n' "$name" >> "$QC/fastqc_status.tsv"
    else
        printf '%s\treport_missing; inspect fastqc.log\n' "$name" >> "$QC/fastqc_status.tsv"
    fi
done
multiqc --force --filename ipspdl_multiqc.html --outdir "$QC" "$QC" >/dev/null 2>&1 || true

printf 'run\tsample\tgroup\tstatus\n' > "$QUANT/quant_status.tsv"
while IFS=$'\t' read -r group sample biosample experiment run library cell_type cell_line provider age sex collection treatment strategy source selection layout instrument; do
    [[ "$run" == "run" ]] && continue
    out="$QUANT/$run"
    log="$QUANT/${run}.log"
    if [[ -s "$out/quant.sf" ]]; then
        printf '%s\t%s\t%s\talready complete\n' "$run" "$sample" "$group" >> "$QUANT/quant_status.tsv"
        continue
    fi
    if [[ -e "$out" ]]; then
        printf '%s\t%s\t%s\tincomplete output directory exists\n' "$run" "$sample" "$group" >> "$QUANT/quant_status.tsv"
        continue
    fi
    args=(quant --index "$INDEX" --libType A --threads "$THREADS" --seqBias --gcBias --output "$out")
    if [[ "$layout" == "paired" ]]; then
        r1="$TMP_READS/${run}_1.fastq.gz"
        r2="$TMP_READS/${run}_2.fastq.gz"
        if [[ ! -s "$r1" || ! -s "$r2" ]]; then
            printf '%s\t%s\t%s\tmissing input\n' "$run" "$sample" "$group" >> "$QUANT/quant_status.tsv"
            continue
        fi
        if salmon "${args[@]}" --mates1 "$r1" --mates2 "$r2" >"$log" 2>&1; then
            printf '%s\t%s\t%s\tpassed\n' "$run" "$sample" "$group" >> "$QUANT/quant_status.tsv"
        else
            printf '%s\t%s\t%s\tfailed; inspect %s\n' "$run" "$sample" "$group" "$(basename "$log")" >> "$QUANT/quant_status.tsv"
        fi
    else
        single="$TMP_READS/${run}.fastq.gz"
        if [[ ! -s "$single" ]]; then
            printf '%s\t%s\t%s\tmissing input\n' "$run" "$sample" "$group" >> "$QUANT/quant_status.tsv"
            continue
        fi
        if salmon "${args[@]}" --unmatedReads "$single" >"$log" 2>&1; then
            printf '%s\t%s\t%s\tpassed\n' "$run" "$sample" "$group" >> "$QUANT/quant_status.tsv"
        else
            printf '%s\t%s\t%s\tfailed; inspect %s\n' "$run" "$sample" "$group" "$(basename "$log")" >> "$QUANT/quant_status.tsv"
        fi
    fi
done < "$REVIEW/ipspdl_rnaseq_manifest.tsv"

cat "$QC/fastqc_status.tsv"
cat "$QUANT/quant_status.tsv"
