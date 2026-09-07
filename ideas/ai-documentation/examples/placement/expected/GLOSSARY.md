# Glossary

| Term | Canonical identifier | Meaning | Defined in | Known aliases | Notes |
|---|---|---|---|---|---|
| confirmation | `shop.service.OrderService.confirm` | A committed order status change followed by synchronous dispatch to any registered OrderConfirmed listeners. | shop/service.py | none | No listeners means no delivery; a listener failure can leave the order confirmed without an inbox entry. |
