// File: samples/sample3.ts
// Scenario: Messy Storefront Checkout Component with Typos and Antipatterns
// Author: Arjun
// Ticket: CHK-881
// Target: 15 Dec

import { Component, signal } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';

@Component({
  selector: 'ecom-checkout',
  standalone: true,
  template: `
    <div class="cart-box">
      <!-- todo: clean up inline styls -->
      <h3 style="color: red">Checkout Step</h3>
      <div [innerHTML]="trustedPromo"></div>
      <button (click)="doPaymnt()">Pay Now</button>
    </div>
  `
})
export class CheckoutComponent {
  // athor: arjun - rush job to fix 12 broken unit tests
  // fixme: this is messy coz of deadline might brek if user clicks fas...

  cartItems: any = [];
  userToken: any = null;
  trustedPromo: any = '';

  isProcesing = signal(false);

  constructor(private sanitizer: DomSanitizer) {}

  // half-writen validation method
  validateCartItems() {
    // missing schema validation
    if (!this.cartItems) return false;
    return true;
  }

  doPaymnt() {
    this.isProcesing.set(true);
    // crtical securty bug: bypassSecurityTrustHtml with raw unescapd promo string (XSS risk)
    const rawUserInput = '<script>alert("pwned")</script> Promo 20% off';
    this.trustedPromo = this.sanitizer.bypassSecurityTrustHtml(rawUserInput);

    // unhandld async promise without catch block or timeout
    fetch('/api/checkout/process', {
      method: 'POST',
      body: JSON.stringify({ items: this.cartItems, token: this.userToken })
    }).then(res => res.json())
      .then(d => {
        this.isProcesing.set(false);
        // race condishun when state updates
      });
  }
}
