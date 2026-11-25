// File: samples/sample4.ts
// Scenario: Minimal User Status Badge Component (Very Short Input)
// Author: Priya
// Ticket: UI-12
// Target: 20 Dec

import { Component, ChangeDetectionStrategy, input } from '@angular/core';

@Component({
  selector: 'app-user-status-badge',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="badge" [class]="statusClass()">
      {{ status() }}
    </span>
  `,
  styles: [`
    .badge { padding: 4px 8px; border-radius: 999px; font-size: 12px; }
    .badge-active { background: #dcfce7; color: #15803d; }
    .badge-offline { background: #f3f4f6; color: #4b5563; }
  `]
})
export class UserStatusBadgeComponent {
  readonly status = input<'active' | 'offline'>('offline');

  statusClass(): string {
    return 'badge-' + this.status();
  }
}
