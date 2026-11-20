"""Default quantity precision shared by runtime and offline inventory checks."""

# Opening stock and historical quantities retain four decimal places.
# Half of the smallest supported increment absorbs floating-point residue.
LEDGER_QUANTITY_DECIMALS = 4
LEDGER_EPS = 0.5 * 10 ** -LEDGER_QUANTITY_DECIMALS
