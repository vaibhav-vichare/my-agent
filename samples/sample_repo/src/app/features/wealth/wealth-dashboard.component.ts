// File: samples/sample1.ts
// Scenario: Wealth Management Dashboard (Angular 21 Standalone Architecture)
// Author: Priya
// Ticket: PORT-102
// Target: 18 Dec

import {
  Component,
  OnInit,
  ChangeDetectionStrategy,
  signal,
  computed,
  input,
  output,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';

export interface PortfolioSummary {
  portfolioId: string;
  totalValue: number;
  unrealizedGain: number;
  allocation: Record<string, number>;
}

@Component({
  selector: 'app-wealth-dashboard',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="dashboard-shell">
      <header class="header">
        <h2>Portfolio: {{ portfolioId() }}</h2>
        <div class="metrics">
          <span>Total: {{ formattedTotal() }}</span>
          <span [class.positive]="unrealizedGain() >= 0">
            Gain: {{ unrealizedGain() }}%
          </span>
        </div>
      </header>
      <section class="allocation">
        @for (item of allocationItems(); track item.asset) {
          <div class="asset-row">
            <span>{{ item.asset }}</span>
            <span>{{ item.percentage }}%</span>
          </div>
        } @empty {
          <p>No asset allocation data available.</p>
        }
      </section>
      <button (click)="refresh.emit()">Refresh Data</button>
    </div>
  `,
})
export class WealthDashboardComponent implements OnInit {
  // Angular 21 Signal Inputs and Outputs
  readonly portfolioId = input.required<string>();
  readonly unrealizedGain = input<number>(0);
  readonly refresh = output<void>();

  // Internal reactive signals
  readonly portfolioData = signal<PortfolioSummary | null>(null);

  // Computed state
  readonly formattedTotal = computed(() => {
    const data = this.portfolioData();
    return data ? '$' + data.totalValue.toLocaleString() : '$0';
  });

  readonly allocationItems = computed(() => {
    const data = this.portfolioData();
    if (!data || !data.allocation) return [];
    return Object.entries(data.allocation).map(([asset, percentage]) => ({
      asset,
      percentage,
    }));
  });

  // Antipattern: Heavy constructor dependency injection instead of modern inject() function
  constructor(
    private http: HttpClient,
    private router: Router
  ) {}

  ngOnInit(): void {
    // Architectural Blocker / Memory Leak:
    // Subscribes directly without takeUntilDestroyed or DestroyRef cleanup
    this.http.get<PortfolioSummary>(`/api/portfolios/${this.portfolioId()}`)
      .subscribe((data) => {
        this.portfolioData.set(data);
      });
  }
}
