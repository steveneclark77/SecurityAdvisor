/* Nonpaginated tables sort their rendered rows; paginated browsers use server links. */
(() => {
  const collator = new Intl.Collator(undefined, {numeric:true, sensitivity:'base'});
  const nameCollator = new Intl.Collator(undefined, {sensitivity:'base'});
  const cellValue = (row,index) => row.cells[index]?.dataset.sortValue ?? row.cells[index]?.textContent.trim() ?? '';
  document.querySelectorAll('table').forEach(table => {
    if (table.hasAttribute('data-server-sort') || table.id === 'result_list' || table.closest('.inline-group')) return;
    if (!table.tHead && table.classList.contains('detail-table') && table.rows[0]?.cells.length === 2) {
      const row=table.createTHead().insertRow();
      for (const label of ['Field','Value']) {const th=document.createElement('th');th.scope='col';th.textContent=label;row.append(th);}
    }
    const headers=Array.from(table.tHead?.rows[0]?.cells || []);
    const body=table.tBodies[0];
    if (!body || !headers.length) return;
    const rows=Array.from(body.rows);
    // A colspan empty state is not sortable record data.
    if (!rows.some(row=>row.cells.length === headers.length)) return;
    const identityIndex = headers.findIndex(header => /^(name|title|code|control|field|version)$/i.test(header.textContent.trim()));
    const identity = identityIndex >= 0 ? identityIndex : headers.findIndex(header => !header.hasAttribute('data-no-sort') && !/^(actions?|select|delete)$/i.test(header.textContent.trim()));
    headers.forEach((header,index) => {
      const label=header.textContent.trim();
      if (header.hasAttribute('data-no-sort') || /^(actions?|select|delete)$/i.test(label) || header.querySelector('input,button,a')) return;
      header.scope='col';
      header.setAttribute('aria-sort','none');
      const button=document.createElement('button');
      button.type='button';button.className='table-sort';
      const text=document.createElement('span');text.textContent=label;
      const arrow=document.createElement('span');arrow.textContent='↕';arrow.setAttribute('aria-hidden','true');
      button.append(text,arrow);button.setAttribute('aria-label',`Sort by ${label} ascending`);
      header.replaceChildren(button);
      button.addEventListener('click',() => {
        const ascending=header.getAttribute('aria-sort') !== 'ascending';
        headers.forEach(th => {if(!th.querySelector('button.table-sort')) return;th.setAttribute('aria-sort','none');const icon=th.querySelector('.table-sort span[aria-hidden]');if(icon) icon.textContent='↕';});
        const sorted=rows.map((row,position)=>({row,position})).sort((a,b)=> {
          const primary = (ascending ? 1 : -1)*collator.compare(cellValue(a.row,index),cellValue(b.row,index));
          const name = identity >= 0 && index !== identity
            ? nameCollator.compare(cellValue(a.row,identity),cellValue(b.row,identity)) : 0;
          return primary || name || a.position-b.position;
        });
        for(const {row} of sorted) body.append(row);
        header.setAttribute('aria-sort',ascending?'ascending':'descending');
        arrow.textContent=ascending?'↑':'↓';
        for (const th of headers) {
          const control=th.querySelector('button.table-sort');
          if(control) control.setAttribute('aria-label',`Sort by ${control.querySelector('span').textContent} ${th.getAttribute('aria-sort') === 'ascending' ? 'descending':'ascending'}`);
        }
      });
    });
  });
})();
