from datetime import datetime


def order_template(order, items):
    items_html = ""

    for item in items:
        items_html += f"""
        <tr>
            <td>{item.get("product_name")}</td>
            <td>{item.get("quantity")}</td>
            <td>Rs. {item.get("price")}</td>
        </tr>
        """

    return f"""
    <html>
    <body>
        <h2>New Order Received</h2>

        <p>
            <strong>Order Number:</strong> #{order.id}
        </p>

        <p>
            <strong>Order Date:</strong>
            {order.created_at.strftime("%d-%m-%Y %I:%M %p")}
        </p>

        <table
            border="1"
            cellpadding="10"
            cellspacing="0"
            style="border-collapse:collapse;width:100%;"
        >
            <thead>
                <tr style="text-align: center">
                    <th>Product</th>
                    <th>Quantity</th>
                    <th>Price</th>
                </tr>
            </thead>

            <tbody>
                {items_html}
            </tbody>
        </table>

        <br>

        <h3>
            Total: Rs. {order.total}
        </h3>

    </body>
    </html>
    """
