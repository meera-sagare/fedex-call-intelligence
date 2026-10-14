import { Component } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink],
  template: `
    <header class="topbar">
      <div class="container bar">
        <a routerLink="/" class="brand" aria-label="Call Intelligence home">
          <span class="mark" aria-hidden="true">ABC</span>
          <span class="name">ABC <span class="product">Call Intelligence</span></span>
        </a>
        <nav class="muted">Collections &amp; Accounts Receivable</nav>
      </div>
    </header>
    <main>
      <router-outlet />
    </main>
    <footer class="footer">
      <div class="container muted">AI-generated notes should be reviewed by the collector before they are finalized.</div>
    </footer>
  `,
  styles: `
    :host {
      display: flex;
      flex-direction: column;
      min-height: 100vh;
    }
    .topbar {
      border-bottom: 1px solid var(--brand-border);
      background: #fff;
    }
    .bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 64px;
      gap: 16px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      text-decoration: none;
    }
    .mark {
      display: grid;
      place-items: center;
      width: 40px;
      height: 40px;
      border-radius: 10px;
      background: var(--brand-purple);
      color: #fff;
      font-weight: 800;
      font-size: 0.85rem;
      letter-spacing: 0.5px;
      box-shadow: inset 0 -4px 0 var(--brand-orange);
    }
    .name {
      color: var(--brand-purple);
      font-weight: 800;
      font-size: 1.25rem;
    }
    .product {
      color: var(--brand-text);
      font-weight: 600;
      letter-spacing: 0;
    }
    nav {
      font-size: 0.9rem;
    }
    main {
      flex: 1;
    }
    .footer {
      border-top: 1px solid var(--brand-border);
      padding: 16px 0;
      font-size: 0.8rem;
      margin-top: 40px;
    }
    @media (max-width: 640px) {
      nav {
        display: none;
      }
    }
  `,
})
export class App {}
