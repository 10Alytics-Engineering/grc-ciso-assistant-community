<script lang="ts">
	import { safeTranslate } from '$lib/utils/i18n';
	interface Props {
		item: any; // Specify the type of 'item' as a key of 'Sidebar'
	}

	let { item }: Props = $props();
</script>

<span
	class="flex-1 text-left whitespace-nowrap"
	data-testid={'accordion-item-' + item.name.toLowerCase().replace(' ', '-')}
>
	{safeTranslate(item.name)}
</span>
