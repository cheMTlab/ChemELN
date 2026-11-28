# People & permissions

Access works in two layers.

## 1. Role in each research group
| | Viewer | Member | PI | Group admin |
|---|---|---|---|---|
| Read the group's notebooks, campaigns, plates, bio records, orders | ✓ | ✓ | ✓ | ✓ |
| Write experiments, campaigns, plates, bio records | | ✓ | ✓ | ✓ |
| Use / move the group's containers, request orders, witness experiments | | ✓ | ✓ | ✓ |
| Approve orders, manage budgets, place orders | | | ✓ | ✓ |
| Manage members | | | ✓ | ✓ (and grant admin) |

## 2. Instance capabilities
Capabilities are granted per person by a user manager or an instance admin. They apply across all groups.

| Capability | Gives |
|---|---|
| User manager | Create, edit and deactivate accounts; manage any group's members |
| Central purchasing | See every order; place orders with suppliers and receive them |
| Order approver | Approve or reject any group's orders |
| Safety officer | See all inventory and safety reports |
| Inventory manager | Manage shared locations and any container |
| Biosafety officer | See every group's strains and plasmids |

**Instance administrators** (Django staff) hold every capability, can create sites and buildings, delete records, and open the Django admin.

Accounts are never deleted, because records keep their author. Deactivate an account instead. Users can sign in with a password plus optional TOTP, or through institutional SSO.
