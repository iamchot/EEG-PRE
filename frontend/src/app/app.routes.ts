import { Routes } from '@angular/router';
import { authGuard, adminGuard, guestGuard, userGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },

  // Guest-only routes
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'register',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/register/register.component').then((m) => m.RegisterComponent),
  },

  // User routes (authenticated)
  {
    path: 'dashboard',
    canActivate: [authGuard, userGuard],
    loadComponent: () =>
      import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
  },
  {
    path: 'persona',
    canActivate: [authGuard, userGuard],
    loadComponent: () =>
      import('./features/persona/persona.component').then((m) => m.PersonaComponent),
  },
  {
    path: 'eeg-session',
    canActivate: [authGuard, userGuard],
    loadComponent: () =>
      import('./features/eeg-session/eeg-session.component').then((m) => m.EegSessionComponent),
  },
  {
    path: 'comic/:id',
    canActivate: [authGuard, userGuard],
    loadComponent: () =>
      import('./features/comic-generation/comic-view.component').then((m) => m.ComicViewComponent),
  },
  {
    path: 'history',
    canActivate: [authGuard, userGuard],
    loadComponent: () =>
      import('./features/history/history.component').then((m) => m.HistoryComponent),
  },

  // Admin routes
  {
    path: 'admin',
    canActivate: [authGuard, adminGuard],
    loadComponent: () =>
      import('./features/admin/admin.component').then((m) => m.AdminComponent),
  },
  {
    path: 'admin/dataset-collection',
    canActivate: [authGuard, adminGuard],
    loadComponent: () =>
      import('./features/dataset-collection/dataset-collection.component')
        .then((m) => m.DatasetCollectionComponent),
  },
  {
    path: 'admin/dataset-collection/sessions/:id/run',
    canActivate: [authGuard, adminGuard],
    loadComponent: () =>
      import('./features/dataset-collection-runner/dataset-collection-runner.component')
        .then((m) => m.DatasetCollectionRunnerComponent),
  },

  // Fallback
  { path: '**', redirectTo: 'dashboard' },
];
