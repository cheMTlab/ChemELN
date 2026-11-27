# Using the inventory

## Concepts
- **Compound**: a substance, shared by the whole instance. Structures are canonicalised with RDKit, and the InChIKey prevents duplicates. Substances without a structure (mixtures, Celite) are allowed.
- **Container**: a physical bottle or vial with its own barcode (`CT…`), amount, group, owner, location, supplier, lot and dates.
- **Location**: a tree. *Site › Building › Room › Cabinet › Shelf* (also fridge, freezer, glovebox, box). A location can list allowed **storage classes**; a container stored where its class is not allowed gets a warning.

## Who can do what
| | Viewer | Member | PI / group admin | Instance admin |
|---|---|---|---|---|
| Find containers (whole instance*) | ✓ | ✓ | ✓ | ✓ |
| Add / use / move containers of the group | | ✓ | ✓ | ✓ |
| Add compounds | | ✓ | ✓ | ✓ |
| Create cabinets/shelves in the group's rooms | | | ✓ | ✓ |
| Create sites, buildings, shared rooms | | | | ✓ |
| Delete records | | | | ✓ (others mark containers "disposed") |

\* Set `CHEMTLAB_INVENTORY_VISIBILITY=group` to restrict searching to the user's own groups.

## Everyday tasks
- **Find:** type a name, CAS number, formula or synonym. You can also *scan a barcode* (USB scanners act as a keyboard) to jump straight to that container. *Draw structure* runs a substructure or similarity search.
- **Add:** *Add container* → find the compound here, look it up in PubChem (if your admin enabled it), or draw it. Then fill in the amount, location and supplier details. Labels print straight away.
- **Use:** on the container page, enter the amount used in any compatible unit (e.g. 250 mg from a 1 g bottle). Empty containers are marked automatically.
- **Labels:** select containers and choose *Print labels*: a 62 × 29 mm label printer roll, or A4 sheets of 3 × 7 (Avery L7160-compatible).
- **Import:** CSV or SDF. *Check file* first: nothing is saved, and every problem row is listed. The import is all-or-nothing.

## Dashboard alerts
Expired, expiring within 30 days, peroxide formers opened more than 6 months ago, low stock (10 % or less left), and storage-class conflicts.

## History
Every change to compounds, locations and containers is recorded with the user and time (visible in Administration → *History*). Each container also has a readable activity timeline.
