qty_steel = 10.237185
price_hoasen = 19764.78
cost_steel = qty_steel * price_hoasen

labor = cost_steel * 0.25
overhead = cost_steel * 0.10
total_cost = cost_steel + labor + overhead

print(f"Cost Steel: {cost_steel}")
print(f"Total Cost (Giá vốn): {total_cost}")
