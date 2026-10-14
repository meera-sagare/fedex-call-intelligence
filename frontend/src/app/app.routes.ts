import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    title: 'My Customers | ABC Call Intelligence',
    loadComponent: () => import('./pages/welcome/welcome').then((m) => m.Welcome),
  },
  {
    path: 'customers/:id',
    title: 'Customer | ABC Call Intelligence',
    loadComponent: () => import('./pages/customer-detail/customer-detail').then((m) => m.CustomerDetail),
  },
  { path: '**', redirectTo: '' },
];
