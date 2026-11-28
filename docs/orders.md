# Reagent orders

Ordering follows the path from a request to a labelled bottle on the shelf. It is modelled on Open Enventory's order system: requests, central purchasing and cost centres.

```
draft → submitted → approved → ordered → partially received → received
              ↘ rejected (with reason; can be edited and resubmitted)     any open state → cancelled
```

| Step | Who |
|---|---|
| Request (draft, submit) | Any member of the group |
| Approve / reject | The group's PI or admin, or anyone with the **order approver** capability. A PI's own requests are approved automatically. |
| Place with supplier (PO number, expected date) | **Central purchasing** capability, or the group's PI |
| Receive | Purchasing, the PI, or any group member |

- **Budgets.** Each group has **cost centres** (grants, accounts), optionally with a budget. An order that would exceed the remaining budget can only be approved with an explicit override, and the override is logged.
- **Receiving** creates one inventory container per package. Each container gets its own barcode, plus the lot number, expiry date and storage location you enter, so labels can be printed straight away.
- **Re-order** from any container page: this creates a draft with the same product, supplier, catalogue number and package size.
- Every step is logged with the user, time and note. Orders also keep a full field history.
