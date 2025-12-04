// Poll /contributions/data and update the UI
(function(){
  const goalEl = document.getElementById('goal');
  const raisedEl = document.getElementById('raised');
  const remainingEl = document.getElementById('remaining');
  const percentEl = document.getElementById('percent');
  const barEl = document.getElementById('progress-bar');
  const paymentsList = document.getElementById('payments-list');

  async function fetchData(){
    try{
      const res = await fetch('/contributions/data');
      if(!res.ok) throw new Error('fetch failed');
      const data = await res.json();
      updateUI(data);
    }catch(e){
      console.error('contrib fetch error', e);
    }
  }

  function fmt(n){
    return Number(n).toLocaleString(undefined, {minimumFractionDigits:0, maximumFractionDigits:2});
  }

  function updateUI(data){
    const target = Number(data.target_amount || 0);
    const total = Number(data.total_contributed || 0);
    const remaining = Number(data.remaining || Math.max(0, target - total));
    const percent = Number(data.percent || 0);

    goalEl.textContent = target ? 'Ksh ' + fmt(target) : '—';
    raisedEl.textContent = 'Ksh ' + fmt(total);
    remainingEl.textContent = 'Ksh ' + fmt(remaining);
    percentEl.textContent = percent + '%';
    barEl.style.width = Math.min(100, Math.max(0, percent)) + '%';

    // payments
    paymentsList.innerHTML = '';
    (data.payments || []).slice().reverse().slice(0,10).forEach(p => {
      const li = document.createElement('li');
      li.style.padding = '8px 10px';
      li.style.borderBottom = '1px solid #eee';
      const name = p.from_name || p.from || 'Anonymous';
      const when = p.timestamp ? new Date(p.timestamp).toLocaleString() : '';
      li.textContent = `${name} — Ksh ${fmt(p.amount)}  ·  ${when}`;
      paymentsList.appendChild(li);
    });
  }

  // Start polling
  fetchData();
  setInterval(fetchData, 5000);

  // Simulate form
  const form = document.getElementById('simulate-form');
  if(form){
    form.addEventListener('submit', async (e) =>{
      e.preventDefault();
      const name = document.getElementById('sim-name').value || 'Sim';
      const amount = Number(document.getElementById('sim-amount').value || 0);
      if(!amount) return alert('Enter an amount');
      try{
        const res = await fetch('/contributions/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,amount})});
        if(!res.ok) throw new Error('simulate failed');
        document.getElementById('sim-amount').value = '';
        fetchData();
      }catch(err){
        alert('Failed to simulate: '+err.message);
      }
    });
  }

})();
