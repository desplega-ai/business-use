/**
 * TSX file — ensure() used inside a React component.
 * Scanner should handle .tsx files and extract the call.
 */
import React from 'react';
import { ensure } from 'business-use';

interface CheckoutButtonProps {
  cartId: string;
  amount: number;
}

export function CheckoutButton({ cartId, amount }: CheckoutButtonProps) {
  const handleClick = () => {
    ensure({
      id: 'checkout_button_clicked',
      flow: 'checkout',
      runId: cartId,
      data: { amount },
      description: 'User clicked checkout button',
    });

    // ... actual checkout logic
  };

  return <button onClick={handleClick}>Checkout (${amount})</button>;
}
