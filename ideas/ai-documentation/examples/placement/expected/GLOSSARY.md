# Glossary

| Term | Canonical identifier | Meaning | Defined in | Known aliases | Notes |
|---|---|---|---|---|---|
| confirmation | `shop.service.OrderService.confirm` | A committed order status change followed by synchronous listener delivery. | shop/service.py | none | A listener failure can leave the order confirmed without an inbox entry. |
