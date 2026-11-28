# Biology: registry, plates and assays

## Registry
- **Plasmids** (`pCT0001`…):
  - backbone, insert, promoter, origin, resistance, tags and copy number;
  - the sequence, with GC content and size calculated automatically;
  - features, shown on a circular or linear **plasmid map**;
  - the Addgene ID and the parent plasmid.

  **Import GenBank** reads the name, topology, features and sequence from a `.gb` file. You can search by any sub-sequence on either strand, and export FASTA.
- **Strains & cell lines** (`ST…`, `CL…`): organism, genotype, plasmids carried, resistance, **biosafety level**, GMO flag, tissue, passage number, mycoplasma test date and source (e.g. ATCC).
- **Oligos** (`OL…`): sequence, purpose, target and modifications. The melting temperature (nearest-neighbour, SantaLucia 1998, with salt correction), GC content and reverse complement are calculated as you type.
- **Samples & stocks**: glycerol stocks, DNA preps, frozen cells, proteins, antibodies and more. Each has a barcode (`BCT…`), a place in the shared location tree with its box position, concentration and volume.

## Well plates
- Formats: 6, 12, 24, 48, 96, 384 or 1536 wells. A new plate can copy the layout of an earlier one.
- **Layout editor**:
  - select wells (click, or click a row letter or column number);
  - set the role (sample, positive or negative control, blank, standard), label, compound, concentration and curve group;
  - exclude outliers.
- **Serial dilution**: fill a row or column with a dilution series (start well, steps, top concentration, factor), with replicates.
- **Import readings** from the plate reader, either pasted or as a file:
  - grid exports (rows A…, one column per plate column);
  - long format (`well,value[,channel,time]`), for kinetics and growth curves.

## Results & QC
- **Heatmap** of the raw signal, or **% effect** (0 % = negative control, 100 % = positive control).
- **Z′ factor** and control statistics (mean, CV), with a plain verdict: excellent, usable, or not usable.
- **Hits**: sample wells at 50 % effect or more.
- **Dose-response**: a 4-parameter logistic fit for each curve group, giving IC50/EC50, Hill slope, top, bottom and R². An IC50 outside the tested concentration range is flagged as extrapolated.
- **Kinetics**: time courses per well, with the maximum specific growth rate.
- **Export CSV**: the layout and every reading in long format.

Biosafety officers (an instance capability) can see the strains and plasmids of every group.
