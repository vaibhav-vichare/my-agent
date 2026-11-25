import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: 'wealth',
    loadComponent: () => import('./features/wealth/wealth-dashboard.component').then(m => m.WealthDashboardComponent)
  },
  {
    path: '',
    redirectTo: 'wealth',
    pathMatch: 'full'
  }
];
