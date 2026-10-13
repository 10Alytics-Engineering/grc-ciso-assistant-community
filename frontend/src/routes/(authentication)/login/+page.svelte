<script lang="ts">
	import type { ActionData, PageData } from './$types';
	import Logo from '$lib/components/Logo/Logo.svelte';
	import icon from '$lib/assets/10a-icon.svg';
	import FormCard from './FormCard.svelte';
	import { m } from '$paraglide/messages';

	interface Props {
		data: PageData;
		form: ActionData;
	}

	let { data, form }: Props = $props();
</script>

<svelte:head>
	<title>10A GRC Lab | {m.login()}</title>
</svelte:head>

<main class="auth-shell">
	<section class="auth-note" aria-labelledby="workspace-heading">
		<!-- .dark scopes the logo's dark: variant so the wordmark reads on this panel in both themes -->
		<div class="dark flex items-center gap-4">
			<Logo />
		</div>
		<div>
			<p class="mb-4 text-[11px] font-extrabold uppercase tracking-[0.18em] text-white/60">
				Governance · Risk · Compliance
			</p>
			<h1 id="workspace-heading">
				{m.yourStreamlined()}
				{m.oneStopShop()}
				{m.forComplianceRiskManagement()}
			</h1>
		</div>
		<p class="text-xs tracking-[0.08em] text-white/60">10Alytics · 10A GRC Lab</p>
	</section>

	<section class="auth-panel" aria-labelledby="sign-in-heading">
		<div class="w-[min(100%,26rem)]">
			<div class="auth-panel__mark">
				<img src={icon} alt="" class="h-9 w-9" />
			</div>
			<p class="eyebrow mb-4">10A GRC Lab</p>
			<h2 id="sign-in-heading" class="text-surface-950-50">{m.logIntoYourAccount()}</h2>
			<p class="mt-4 leading-relaxed text-surface-600-400">{m.youNeedToLogIn()}</p>
			<div class="mt-7">
				<FormCard {data} {form} />
				<p class="mt-6 text-center text-xs text-surface-600-400">
					Powered by 10Alytics ·
					<a
						class="underline"
						href="https://github.com/10Alytics-Engineering/grc-ciso-assistant-community"
						target="_blank"
						rel="noopener noreferrer">Source code (AGPL-3.0)</a
					>
				</p>
			</div>
		</div>
	</section>
</main>
