# Lab notebook (ELN)

## Structure
**Projects** group the **experiments** of a research group. Each experiment gets a notebook code made of the author's initials and a number (`AB-0042`). The code goes on labels, sample vials and the products the experiment creates.

## A synthesis, step by step
1. **New experiment.** Pick the group and project. Optionally start from a **template** (for example "Fischer esterification") that pre-fills the procedure and reagent rows.
2. **Draw the reaction** in the structure editor, or paste a reaction SMILES (`A.B>>C`). Reactants and products become rows of the stoichiometry table, with molar masses calculated by RDKit.
3. **Set the scale** on the limiting reagent by entering its mass, volume or mmol. Give the other rows **equivalents**. CheMTlab calculates the amounts from molar mass, density, purity and molarity:
   - mmol;
   - mass;
   - volume. For solutions, volume comes from molarity, e.g. "1.0 M in THF".
4. **Link bottles.** Choose the actual inventory container for each reagent. Density, purity and molarity are filled in from the bottle.
5. **Deduct from inventory** once you have weighed everything out. The used amounts are booked out of the bottles, once per row, and logged in each bottle's history.
6. **Results.** Enter the isolated mass to get the yield, corrected for purity. Choose **To inventory** to register the product as a new barcoded container. Its lot number is the notebook code.
7. **Procedure, observations, work-up, conclusion.** Write these in free text.
8. **Attachments.** Upload NMR, MS, HPLC and other files. Each file is stored with its SHA-256 checksum.
9. **Sign.** The record becomes immutable. A colleague from the group then **witnesses** it.

## Signatures and integrity
- Signing stores a SHA-256 hash of the experiment's content in an append-only **signature ledger**. Each ledger entry includes the hash of the previous one (a hash chain).
- **Verify signatures** recomputes the hash. Any change made behind the application's back, for example directly in the database, shows up as "content has changed".
- After signing, only status, tags, project and completion date can change. Corrections go in as **addenda**: comments marked as such, with the author and time.
- Use **Repeat / scale up** to start a new draft from a signed experiment. The copy keeps a reference to the original.
