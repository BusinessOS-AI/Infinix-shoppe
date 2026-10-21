const countryCurrency={IN:"INR"};
const countryNames=new Intl.DisplayNames(["en"],{type:"region"});
const savedCatalogVersion=localStorage.getItem("infinix-catalog-version");
let products=savedCatalogVersion?JSON.parse(localStorage.getItem("infinix-products")||"[]"):[];
if(!savedCatalogVersion){localStorage.setItem("infinix-products","[]");localStorage.setItem("shoply-cart","{}");localStorage.setItem("infinix-catalog-version","2")}
let cart=JSON.parse(localStorage.getItem("shoply-cart")||"{}"),wish=JSON.parse(localStorage.getItem("shoply-wish")||"[]"),activeFilter="all",searchTerm="",visibleCount=8,categoryBrowseMode=false;
let accounts=JSON.parse(localStorage.getItem("infinix-accounts")||"[]");
let bargainState=(()=>{try{return JSON.parse(localStorage.getItem("infinix-cart-bargain")||"null")||{signature:"",offer:0,step:0,applied:0,messages:[]}}catch{return{signature:"",offer:0,step:0,applied:0,messages:[]}}})();
let orderHistory=JSON.parse(localStorage.getItem("infinix-orders")||"[]");orderHistory.forEach(order=>{order.currency="INR"});

let country="IN",currentRole=localStorage.getItem("infinix-role")||"customer",currentUser=JSON.parse(localStorage.getItem("infinix-user")||"null");
function freeDeliveryThreshold(){return 499}
const defaultLocations={IN:{city:"New Delhi",state:"Delhi",landmark:"",postal:"110001"}};
let deliveryLocations=JSON.parse(localStorage.getItem("infinix-delivery-locations")||"{}"),deliveryLocation=deliveryLocations[country]||defaultLocations[country]||{city:countryNames.of(country),postal:""};
let pendingCheckout=false;
let activityLog=JSON.parse(localStorage.getItem("infinix-activity-log")||"[]");
let plusMembers=JSON.parse(localStorage.getItem("infinix-plus-members")||"{}");
let membershipRequests=JSON.parse(localStorage.getItem("infinix-plus-requests")||"[]");
let plusPlanPrices=JSON.parse(localStorage.getItem("infinix-plus-plan-prices")||"null")||{monthly:300,quarterly:475,yearly:750};
if(!localStorage.getItem("infinix-plus-plan-prices"))localStorage.setItem("infinix-plus-plan-prices",JSON.stringify(plusPlanPrices));
let selectedPlusPlan="monthly";
let promotionSettings=JSON.parse(localStorage.getItem("infinix-promotion-settings")||"null")||{kicker:"GOOD STUFF, LOWER PRICES",title:"Today’s little obsessions.",description:"A few things we think you'll love—at prices worth a second look.",endAt:Date.now()+8*3600*1000+24*60*1000+12*1000};
if(!promotionSettings.endAt)promotionSettings.endAt=Date.now()+8*3600*1000+24*60*1000+12*1000;
if(!localStorage.getItem("infinix-promotion-settings"))localStorage.setItem("infinix-promotion-settings",JSON.stringify(promotionSettings));
let vouchers=JSON.parse(localStorage.getItem("infinix-vouchers")||"[]"),appliedVoucher=localStorage.getItem("infinix-applied-voucher")||"";
if(currentRole!=="customer"&&(!currentUser||currentUser.role!==currentRole))currentRole="customer";
let authRoleOverride=null;
const grid=document.getElementById("productGrid");

function money(n){const currency=countryCurrency[country]||"INR";let locale="en-IN";try{locale="en-"+country;return new Intl.NumberFormat(locale,{style:"currency",currency,maximumFractionDigits:2}).format(Number(n))}catch{return new Intl.NumberFormat("en-IN",{style:"currency",currency,maximumFractionDigits:2}).format(Number(n))}}
function moneyWhole(n){const currency=countryCurrency[country]||"INR";let locale="en-IN";try{locale="en-"+country;return new Intl.NumberFormat(locale,{style:"currency",currency,maximumFractionDigits:0}).format(Number(n))}catch{return new Intl.NumberFormat("en-IN",{style:"currency",currency,maximumFractionDigits:0}).format(Number(n))}}

const selectedSpecs={category:"all",brand:"",size:"",color:"",material:"",availability:"",sort:""};
function productSpec(product,key){
  const direct=product&&product[key];
  if(direct!==undefined&&direct!==null&&String(direct).trim())return String(direct).trim();
  const specs=product&&product.specifications;
  if(specs&&specs[key]!==undefined&&String(specs[key]).trim())return String(specs[key]).trim();
  const description=String(product&&product.description||"");
  const match=description.match(new RegExp("(?:^|[\\n,;|])\\s*"+key+"\\s*[:=–-]\\s*([^\\n,;|]+)","i"));
  return match?match[1].trim():"";
}
function productMatchesSearch(product){
  const searchable=[product.name,product.category,product.badge,product.description,product.brand,product.size,product.color,product.material,...Object.values(product.specifications||{})].join(" ").toLowerCase();
  return !searchTerm||searchable.includes(searchTerm.toLowerCase());
}
function filteredProducts(){
  const category=selectedSpecs.category&&selectedSpecs.category!=="all"?selectedSpecs.category:activeFilter;
  let list=products.filter(p=>(category==="all"||String(p.category||"").toLowerCase()===category.toLowerCase())&&productMatchesSearch(p));
  for(const key of ["brand","size","color","material"]){const wanted=selectedSpecs[key];if(wanted)list=list.filter(p=>productSpec(p,key).toLowerCase()===wanted.toLowerCase())}
  if(selectedSpecs.availability==="in-stock")list=list.filter(p=>!productStock(p));
  if(selectedSpecs.availability==="out-of-stock")list=list.filter(productStock);
  if(selectedSpecs.sort==="price-asc")list.sort((a,b)=>Number(a.price)-Number(b.price));
  if(selectedSpecs.sort==="price-desc")list.sort((a,b)=>Number(b.price)-Number(a.price));
  if(selectedSpecs.sort==="newest")list.sort((a,b)=>Number(b.id)-Number(a.id));
  return list;
}
function renderFilterOptions(){
  const toolbar=document.getElementById("productFilters");if(!toolbar)return;
  const categorySelect=toolbar.querySelector(`[data-product-filter="category"]`);if(categorySelect)categorySelect.value=selectedSpecs.category&&selectedSpecs.category!=="all"?selectedSpecs.category:activeFilter;
  const facets={brand:"Brand",size:"Size",color:"Color",material:"Material"};
  for(const [key,label] of Object.entries(facets)){
    const select=toolbar.querySelector(`[data-product-filter="${key}"]`);if(!select)continue;
    const current=selectedSpecs[key];
    const values=[...new Set(products.map(p=>productSpec(p,key)).filter(Boolean))].sort((a,b)=>a.localeCompare(b,undefined,{sensitivity:"base"}));
    select.innerHTML=`<option value="">All ${label}s</option>`+values.map(value=>`<option value="${escapeAdminText(value)}">${escapeAdminText(value)}</option>`).join("");
    select.value=values.find(value=>value.toLowerCase()===current.toLowerCase())||"";
    if(current&&!select.value)selectedSpecs[key]="";
  }
}
function renderProducts(){
  renderFilterOptions();
  const all=filteredProducts(),items=all.slice(0,visibleCount);
  grid.innerHTML=items.length?items.map(p=>'<article class="product-card"><div class="product-image"><img src="'+p.image+'" alt="'+p.name+'" loading="lazy"><span class="product-badge">'+p.badge+'</span><button class="heart '+(wish.includes(p.id)?"liked":"")+'" data-wish="'+p.id+'" aria-label="Add to wishlist">'+(wish.includes(p.id)?"♥":"♡")+'</button></div><div class="product-info"><div class="product-cat">'+p.category+(productSpec(p,"brand")?' · '+productSpec(p,"brand"):"")+'</div><div class="product-name">'+p.name+'</div><div class="product-description">'+(p.description||'')+'</div>'+(productStock(p)?'<small class="stock-unavailable">Out of stock</small>':Number.isFinite(Number(p.quantity))?'<small class="stock-available">'+p.quantity+' available</small>':'')+(isFashionProduct(p)?'<button type="button" class="tryon-trigger" data-tryon="'+p.id+'">✦ Try on your photo</button>':'')+'<div class="rating">★★★★★ <span>'+p.rating+' ('+p.reviews+')</span></div><div class="price-row"><span class="price">'+money(p.price)+'</span><span class="old-price">'+money(p.old)+'</span><button class="add-btn" data-add="'+p.id+'" aria-label="Add '+p.name+' to cart" '+(productStock(p)?'disabled title="Out of stock"':'')+'>'+(productStock(p)?'×':'+')+'</button></div></div></article>').join(''):'<div class="no-results"><b>No products match these filters.</b>Try changing or clearing a filter.</div>';
  grid.querySelectorAll(".add-btn").forEach(b=>b.style.display=currentRole==="customer"?"":"none");
  const more=document.getElementById("showMore");more.style.display=all.length>visibleCount?"inline-block":"none";
  const count=document.getElementById("filterResultCount");if(count)count.textContent=`${all.length} product${all.length===1?"":"s"}`;
}
function clearProductFilters(){activeFilter=categoryBrowseMode?activeFilter:"all";searchTerm="";Object.keys(selectedSpecs).forEach(key=>selectedSpecs[key]="");selectedSpecs.category=categoryBrowseMode?activeFilter:"all";document.getElementById("productSearch").value="";document.getElementById("searchInput").value="";renderProducts();}

function isFashionProduct(product){return /fashion/i.test(String(product&&product.category||""))}
function productStock(p){const quantity=Number(p.quantity);return p.outOfStock===true||Number.isFinite(quantity)&&quantity<=0}
function removeCartProduct(product,notify=true){const id=String(product?.id);if(!id||!Object.prototype.hasOwnProperty.call(cart,id))return false;delete cart[id];saveCart();if(notify)toast("“"+product.name+"” is no longer available and was removed from your cart.");return true}
function cartSignature(){return Object.keys(cart).sort().map(id=>id+":"+Number(cart[id]||0)).join("|")}
function saveBargain(){localStorage.setItem("infinix-cart-bargain",JSON.stringify(bargainState))}
function resetBargainForCart(){const signature=cartSignature();if(signature!==bargainState.signature){bargainState={signature,offer:0,step:0,applied:0,messages:signature?[{by:"bot",text:"Hi! I can start with 2% off. Ask me for a better deal to negotiate, up to 6%. If you name a specific 2%–6% discount, I’ll offer half of what you requested."}]:[]};saveBargain()}}
function activeBargainPercent(){return bargainState.signature===cartSignature()?Math.min(6,Math.max(0,Number(bargainState.applied)||0)):0}
function bargainAmount(subtotal){return Math.round(subtotal*activeBargainPercent())/100}
function renderBargainChat(){const list=document.getElementById("bargainMessages"),accept=document.getElementById("acceptBargain"),status=document.getElementById("bargainStatus");if(!list)return;list.innerHTML=bargainState.messages.map(message=>{const bubble=document.createElement("div");bubble.className="bargain-message "+(message.by==="customer"?"customer-message":"bot-message");bubble.textContent=message.text;return bubble.outerHTML}).join("");list.scrollTop=list.scrollHeight;if(accept){accept.disabled=!(bargainState.offer>0);accept.textContent=bargainState.offer?`Accept ${Math.max(Number(bargainState.offer)||0,Number(bargainState.applied)||0)}% deal`:"Accept deal"}if(status)status.textContent=activeBargainPercent()?`${activeBargainPercent()}% deal applied to this cart.`:"Your deal applies to this cart only."}
function bargainReply(text){
  const requested=text.match(/(\d+(?:\.\d+)?)\s*%/),more=/\b(more|better|increase|higher|another|again)\b/i.test(text),decline=/\b(no|cancel|remove|stop|clear)\b/i.test(text);
  if(decline){bargainState.offer=0;bargainState.applied=0;bargainState.messages.push({by:"bot",text:"No problem. I’ve removed the bargaining discount."});return}
  if(requested){const amount=Number(requested[1]);if(amount>=2&&amount<=6){const requestedOffer=amount/2;bargainState.offer=Math.max(requestedOffer,Number(bargainState.applied)||0);bargainState.messages.push({by:"bot",text:bargainState.offer>requestedOffer?`Your existing ${bargainState.offer}% deal is better than half of the ${amount}% you requested. You can keep it.`:`You asked for ${amount}% off. I can offer half: ${bargainState.offer}% off this cart.`});return}if(amount>6){bargainState.offer=Math.max(3,Number(bargainState.applied)||0);bargainState.messages.push({by:"bot",text:bargainState.offer>3?`I can’t go above 6%; your existing ${bargainState.offer}% offer is better than half of the 6% maximum.`:"I can’t go above 6%. As requested, I can offer half of the 6% maximum: 3% off."});return}}
  function saveCart(){localStorage.setItem("shoply-cart",JSON.stringify(cart));resetBargainForCart();renderCart()}
function renderCart(){
  const ids=Object.keys(cart).map(Number).filter(id=>products.some(p=>p.id===id&&!productStock(p)));
  const count=ids.reduce((sum,id)=>sum+(Number(cart[id])||0),0);
  const sum=ids.reduce((total,id)=>total+products.find(p=>p.id===id).price*cart[id],0);
  const threshold=freeDeliveryThreshold();
  const thresholdFree=sum>0&&(sum>=threshold||isPlusMember());
  const delivery=sum===0||thresholdFree?0:(countryCurrency[country]==="INR"?49:5);
  const voucher=vouchers.find(item=>item.code===appliedVoucher&&item.active&&(!item.membersOnly||isPlusMember())&&sum>=Number(item.minimum||0));
  const discount=voucher?Math.min(sum,Number(voucher.amount)||0):0;
  const bargain=bargainAmount(sum);
  if(appliedVoucher&&!voucher){appliedVoucher="";localStorage.removeItem("infinix-applied-voucher")}
  const total=Math.max(0,sum+delivery-discount-bargain);
  document.getElementById("cartCount").textContent=count;
  document.getElementById("cartTitleCount").textContent="("+count+")";
  document.getElementById("subtotal").textContent=money(sum);
  const bargainDiscountEl=document.getElementById("bargainDiscount"),voucherDiscountEl=document.getElementById("voucherDiscount"),voucherNoteEl=document.getElementById("voucherCartNote");
  if(bargainDiscountEl)bargainDiscountEl.textContent=bargain?"−"+money(bargain)+" ("+activeBargainPercent()+"%)":"—";
  if(voucherDiscountEl)voucherDiscountEl.textContent=discount?"−"+money(discount):"—";
  if(voucherNoteEl)voucherNoteEl.textContent=voucher?`${voucher.code} applied · You saved ${money(discount)}`:"Use an active voucher from the offers above.";
  document.getElementById("deliveryCost").textContent=thresholdFree?"FREE":sum?money(delivery):"—";
  document.getElementById("cartTotal").textContent=money(total);
  document.getElementById("checkoutTotal").textContent=money(total)+" →";
  document.getElementById("shippingProgress").style.width=Math.min(100,threshold?sum/threshold*100:0)+"%";
  document.getElementById("shippingMsg").textContent=thresholdFree?"You've unlocked free delivery!":sum?"Add "+money(Math.max(0,threshold-sum))+" to unlock free delivery":"Free delivery on orders of ₹499 or more";
  resetBargainForCart();renderBargainChat();
  const box=document.getElementById("cartItems");
  box.innerHTML=ids.length?ids.map(id=>{const p=products.find(item=>item.id===id),quantity=Math.max(1,Number(cart[id])||1),stock=Number(p.quantity),atStockLimit=Number.isFinite(stock)&&quantity>=stock;return '<div class="cart-item"><img src="'+p.image+'" alt=""><div class="cart-item-info"><b>'+p.name+'</b><small>'+p.category+'</small><div class="cart-item-bottom"><div class="qty" aria-label="Quantity controls"><button type="button" data-qty="'+id+'" data-change="-1" aria-label="Decrease quantity or remove item" title="Decrease quantity">−</button><span aria-live="polite">'+quantity+'</span><button type="button" data-qty="'+id+'" data-change="1" aria-label="Increase quantity" title="Increase quantity" '+(atStockLimit?'disabled aria-disabled="true"':'')+'>+</button></div><b>'+money(p.price*quantity)+'</b></div></div><button class="remove" data-remove="'+id+'">Remove</button></div>'}).join(''):'<div class="empty-cart"><div>♡</div><b>Your cart is taking a little break.</b><p>Add something lovely to get started.</p></div>';
}
function toast(msg){const t=document.getElementById("toast");if(!t)return;t.textContent=msg;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2200)}
function openPanel(el){document.getElementById("overlay").classList.add("open");el.classList.add("open")}
function closePanels(){document.getElementById("overlay").classList.remove("open");document.querySelectorAll(".drawer,.modal").forEach(x=>x.classList.remove("open"));stopVisualCamera();clearTryOnPhoto()}
  grid.addEventListener("click",e=>{
  let a=e.target.closest("[data-add]"),h=e.target.closest("[data-wish]");
  if(a){
    let id=a.dataset.add,product=products.find(p=>String(p.id)===String(id));
    if(!product||productStock(product)){toast("This product is out of stock");return}
    if(Number.isFinite(Number(product.quantity))&&(cart[id]||0)>=Number(product.quantity)){toast("That is all the available stock");return}
    cart[id]=(cart[id]||0)+1;saveCart();logActivity("Product added to cart",product.name);toast("Added to your cart — nice choice!");
  }
  if(h){
    let id=Number(h.dataset.wish);
    wish=wish.includes(id)?wish.filter(x=>x!==id):[...wish,id];
    localStorage.setItem("shoply-wish",JSON.stringify(wish));
    logActivity(wish.includes(id)?"Product added to wishlist":"Product removed from wishlist",products.find(p=>p.id===id)?.name||"Product");
    renderProducts();toast(wish.includes(id)?"Saved to your wishlist":"Removed from your wishlist");
  }
});

document.getElementById("cartItems").addEventListener("click",e=>{
  let q=e.target.closest("[data-qty]"),r=e.target.closest("[data-remove]");
  if(q){
    let id=q.dataset.qty,next=(Number(cart[id])||0)+Number(q.dataset.change),product=products.find(item=>String(item.id)===String(id));
    if(next<=0)delete cart[id];
    else if(!product||productStock(product)){delete cart[id];toast("This product is no longer available and was removed from your cart")}
    else if(Number.isFinite(Number(product.quantity))&&next>Number(product.quantity)){toast("That is all the available stock");return}
    else cart[id]=next;
    saveCart();
  }
  if(r){delete cart[r.dataset.remove];saveCart()}
});

document.querySelectorAll(".filter").forEach(b=>b.onclick=()=>{
  document.querySelectorAll(".filter").forEach(x=>x.classList.remove("active"));
  b.classList.add("active");
  activeFilter=b.dataset.filter;
  selectedSpecs.category=activeFilter;
  visibleCount=8;
  renderProducts();
});

const categoryDetails={
  Tech:{title:"Tech & gadgets",description:"Discover electronics and smart everyday picks listed by our sellers."},
  Home:{title:"Home & living",description:"Browse seller-listed pieces for your home, comfort, and daily routines."},
  Fashion:{title:"Fashion finds",description:"Explore clothing and accessories from Infinix Shopee sellers."},
  Beauty:{title:"Beauty & care",description:"Shop beauty and personal-care finds listed by our sellers."},
  Other:{title:"Other finds",description:"Explore more products listed by Infinix Shopee sellers."}
};

function openCategory(category){
  const key=Object.keys(categoryDetails).find(name=>name.toLowerCase()===String(category||"").toLowerCase());
  if(!key)return;
  activeFilter=key;
  Object.keys(selectedSpecs).forEach(name=>selectedSpecs[name]="");
  selectedSpecs.category=key;
  searchTerm="";
  document.getElementById("productSearch").value="";
  document.getElementById("searchInput").value="";
  categoryBrowseMode=true;
  document.querySelector(`[data-product-filter="category"]`).closest("label").classList.add("hidden");
  document.body.classList.add("category-browse-mode");
  const header=document.getElementById("categoryBrowseHeader"),details=categoryDetails[key];
  header.classList.remove("hidden");
  document.getElementById("categoryBrowseTitle").textContent=details.title;
  document.getElementById("categoryBrowseDescription").textContent=details.description;
  document.querySelectorAll(".filter").forEach(button=>button.classList.toggle("active",button.dataset.filter===key));
  renderProducts();
  document.getElementById("popular").scrollIntoView({behavior:"smooth",block:"start"});
}

function closeCategory(){
  categoryBrowseMode=false;
  document.body.classList.remove("category-browse-mode");
  document.getElementById("categoryBrowseHeader").classList.add("hidden");
  document.querySelector(`[data-product-filter="category"]`).closest("label").classList.remove("hidden");
  activeFilter="all";
  selectedSpecs.category="all";
  searchTerm="";
  document.getElementById("productSearch").value="";
  document.getElementById("searchInput").value="";
  renderProducts();
  document.getElementById("home").scrollIntoView({behavior:"smooth",block:"start"});
}

function doSearch(source){
  let query=(source!==undefined?source:(document.getElementById("searchInput").value||document.getElementById("productSearch").value)).trim();
  searchTerm=query;
  activeFilter=categoryBrowseMode?activeFilter:"all";
  selectedSpecs.category=categoryBrowseMode?activeFilter:"all";
  document.getElementById("searchInput").value=query;
  document.getElementById("productSearch").value=query;
  visibleCount=12;
  renderProducts();
  document.getElementById("popular").scrollIntoView({behavior:"smooth"});
}
  document.getElementById("searchBtn").onclick=()=>doSearch(document.getElementById("searchInput").value);
document.getElementById("searchInput").addEventListener("keydown",e=>{if(e.key==="Enter")doSearch(e.target.value)});
document.getElementById("productSearchBtn").onclick=()=>doSearch(document.getElementById("productSearch").value);
document.getElementById("productSearch").addEventListener("keydown",e=>{if(e.key==="Enter")doSearch(e.target.value)});

document.getElementById("showMore").onclick=()=>{visibleCount=12;renderProducts()};

const filterToggle=document.getElementById("toggleProductFilters"),filterPanel=document.getElementById("productFilters");
filterToggle.addEventListener("click",()=>{
  const open=filterPanel.classList.toggle("open");
  filterToggle.setAttribute("aria-expanded",String(open));
  filterToggle.classList.toggle("active",open);
});

document.getElementById("productFilters").addEventListener("change",event=>{
  const control=event.target.closest("[data-product-filter]");
  if(!control)return;
  selectedSpecs[control.dataset.productFilter]=control.value;
  if(control.dataset.productFilter==="category"){
    activeFilter=control.value;
    document.querySelectorAll(".filter").forEach(button=>button.classList.toggle("active",button.dataset.filter===activeFilter));
  }
  visibleCount=12;
  renderProducts();
});

document.getElementById("clearProductFilters").addEventListener("click",clearProductFilters);

let tryOnPhotoUrl=null,tryOnProductId=null;

function clearTryOnPhoto(){
  if(tryOnPhotoUrl){URL.revokeObjectURL(tryOnPhotoUrl);tryOnPhotoUrl=null}
  const photo=document.getElementById("tryOnPerson"),
        garment=document.getElementById("tryOnGarment"),
        placeholder=document.getElementById("tryOnPlaceholder");
  if(photo){photo.removeAttribute("src");photo.classList.add("hidden")}
  if(garment){garment.removeAttribute("src");garment.classList.add("hidden")}
  if(placeholder)placeholder.classList.remove("hidden");
  const input=document.getElementById("tryOnPhoto");
  if(input)input.value="";
}

function openTryOn(productId){
  const product=products.find(item=>String(item.id)===String(productId));
  if(!product||!isFashionProduct(product)){toast("Photo try-on is available for Fashion items only");return}
  if(currentRole!=="customer"){toast("Sign in as a customer to use photo try-on");return}
  tryOnProductId=String(product.id);
  const photo=document.getElementById("tryOnPerson"),
        garment=document.getElementById("tryOnGarment"),
        stage=document.getElementById("tryOnStage");
  clearTryOnPhoto();
  tryOnProductId=String(product.id);
  document.getElementById("tryOnProductName").textContent=product.name||"Fashion item";
  document.getElementById("tryOnProductPrice").textContent=money(product.price);
  const productImage=document.getElementById("tryOnProductImage");
  productImage.src=product.image||"";
  productImage.alt=product.name||"Fashion item";
  garment.src=product.image||"";
  garment.classList.remove("hidden");
  stage.style.setProperty("--tryon-scale","45%");
  stage.style.setProperty("--tryon-top","42%");
  document.getElementById("tryOnScale").value="45";
  document.getElementById("tryOnPosition").value="42";
  openPanel(document.getElementById("tryOnModal"));
}

grid.addEventListener("click",event=>{
  const button=event.target.closest("[data-tryon]");
  if(button)openTryOn(button.dataset.tryon);
});

document.getElementById("tryOnPhoto").addEventListener("change",event=>{
  const file=event.target.files&&event.target.files[0];
  if(!file)return;
  if(!file.type.startsWith("image/")){toast("Choose an image file for the try-on preview");event.target.value="";return}
  if(file.size>12*1024*1024){toast("Choose a photo smaller than 12 MB");event.target.value="";return}
  clearTryOnPhoto();
  tryOnPhotoUrl=URL.createObjectURL(file);
  const photo=document.getElementById("tryOnPerson");
  photo.onload=()=>{
    photo.classList.remove("hidden");
    document.getElementById("tryOnPlaceholder").classList.add("hidden");
  };
  photo.onerror=()=>{
    clearTryOnPhoto();
    toast("Could not open that photo. Please choose another.");
  };
  photo.src=tryOnPhotoUrl;
  const product=products.find(item=>String(item.id)===tryOnProductId);
  if(product){
    const garment=document.getElementById("tryOnGarment");
    garment.src=product.image||"";
    garment.classList.remove("hidden");
  }
});

document.getElementById("tryOnScale").addEventListener("input",event=>
  document.getElementById("tryOnStage").style.setProperty("--tryon-scale",event.target.value+"%")
);

document.getElementById("tryOnPosition").addEventListener("input",event=>
  document.getElementById("tryOnStage").style.setProperty("--tryon-top",event.target.value+"%")
);

document.getElementById("tryOnAdd").addEventListener("click",()=>{
  const product=products.find(item=>String(item.id)===tryOnProductId);
  if(!product||productStock(product)){toast("This fashion item is out of stock");return}
  if(Number.isFinite(Number(product.quantity))&&(cart[product.id]||0)>=Number(product.quantity)){toast("That is all the available stock");return}
  cart[product.id]=(cart[product.id]||0)+1;
  saveCart();
  logActivity("Fashion item added from photo try-on",product.name);
  closePanels();
  toast("Added to your cart");
});
  function appendSupportMessage(text,side="assistant",options={}){
  const list=document.getElementById("supportChatMessages");
  const bubble=document.createElement("div");
  bubble.className="support-message "+(side==="customer"?"customer-message":"assistant-message");
  bubble.textContent=text;
  list.appendChild(bubble);

  if(options.contact){
    const links=document.createElement("div");
    links.className="support-contact-links";

    const email=document.createElement("a");
    email.href="mailto:infinix.shoppeenow@gmail.com";
    email.textContent="✉ infinix.shoppeenow@gmail.com";

    const phone=document.createElement("a");
    phone.href="https://wa.me/918643005054";
    phone.target="_blank";
    phone.rel="noopener noreferrer";
    phone.textContent="WhatsApp: +91 86430 05054";

    links.append(email,phone);
    list.appendChild(links);
  }

  if(options.products&&options.products.length){
    options.products.forEach(product=>{
      const card=document.createElement("div");
      card.className="support-product-card";

      const title=document.createElement("b");
      title.textContent=product.name;

      const detail=document.createElement("small");
      detail.textContent=(product.category||"")+" · "+money(product.price);

      const button=document.createElement("button");
      button.type="button";
      button.textContent="View product";
      button.dataset.supportProduct=String(product.id);

      card.append(title,detail,button);
      list.appendChild(card);
    });
  }

  if(options.vouchers&&options.vouchers.length){
    options.vouchers.forEach(voucher=>{
      const card=document.createElement("div");
      card.className="support-voucher-card";

      const code=document.createElement("b");
      code.textContent=voucher.code;

      const amount=document.createElement("small");
      amount.textContent="Save "+money(voucher.amount)+
        (Number(voucher.minimum)>0
          ?" on orders over "+money(voucher.minimum)
          :"");

      const button=document.createElement("button");
      button.type="button";
      button.textContent="Apply in cart";
      button.dataset.supportVoucher=voucher.code;

      card.append(code,amount,button);
      list.appendChild(card);
    });
  }

  list.scrollTop=list.scrollHeight;
}

function answerSupportQuestion(question){
  const q=String(question||"").toLowerCase().trim();
  const member=isPlusMember();

  if(/\b(hi|hello|hey|namaste)\b/.test(q)){
    return {
      text:"Hello! Tell me what you’re shopping for or what you need help with."
    };
  }

  if(/\b(return|returns|exchange|refund)\b/.test(q)){
    return {
      text:"Returns and exchanges can be requested within 7 calendar days after delivery. Keep the item unused with its accessories and original packaging, then contact support with your order number.",
      contact:true
    };
  }

  if(/\b(delivery|shipping|deliver|ship|arrive|free delivery)\b/.test(q)){
    return {
      text:"Orders of ₹499 or more qualify for free delivery. Standard delivery is estimated at 2 days; active Infinix Plus members receive a 1-day estimate. You’ll see the estimate in your order details."
    };
  }

  if(/\b(track|tracking|order|orders|purchase)\b/.test(q)){
    if(!currentUser||currentRole!=="customer"){
      return {
        text:"Please sign in to your customer account, then open Returns & Orders to see your order status and estimated delivery date."
      };
    }

    const key=String(currentUser.username||currentUser.email||"").toLowerCase();

    const mine=orderHistory
      .filter(order=>String(order.customer||"").toLowerCase()===key)
      .sort((a,b)=>new Date(b.createdAt)-new Date(a.createdAt));

    if(!mine.length){
      return {
        text:"I couldn’t find an order on this account yet. After checkout, your order and estimated delivery date will appear under Returns & Orders."
      };
    }

    const order=mine[0];
    const date=order.estimatedDate
      ?new Date(order.estimatedDate).toLocaleDateString("en-IN",{
        day:"numeric",
        month:"short",
        year:"numeric"
      })
      :"not available";

    return {
      text:"Your latest order #"+order.id+
        " is “"+(order.status||"Processing")+
        "”. Estimated delivery: "+date+
        ". Items: "+(order.items||[]).map(item=>item.name).join(", ")+"."
    };
  }

  if(/\b(plus|premium|membership|member)\b/.test(q)){
    return {
      text:member
        ?"Your Infinix Plus membership is active. It includes one-day delivery, free delivery, early offer access, priority support, and members-only deals. Visit the Plus section for your pass and voucher wallet."
        :"Infinix Plus offers one-day delivery, free delivery, early offer access, priority support, and members-only deals. Visit the Plus section to view plans and request membership."
    };
  }

  if(/\b(voucher|coupon|discount|offer)\b/.test(q)){
    const available=vouchers.filter(v=>
      v.active&&(!v.membersOnly||member)
    );

    return available.length
      ?{
        text:"Here are the active offers available to you. You can apply a voucher from your cart.",
        vouchers:available
      }
      :{
        text:member
          ?"There are no active vouchers right now. Check the deals section again soon."
          :"Some vouchers are reserved for Infinix Plus members. Join Plus to unlock member-only offers."
      };
  }

  if(/\b(payment|pay|card|checkout)\b/.test(q)){
    return {
      text:"You can review delivery and payment details at checkout. This storefront currently does not process real card payments; don’t enter real card details. Contact support if you need help with an order.",
      contact:true
    };
  }

  if(/\b(account|sign in|login|password|register|create account)\b/.test(q)){
    return {
      text:"Tap Account & Lists to sign in or create an account. Use your username or email and password. Choose Customer during sign-up to shop and track orders."
    };
  }

  if(/\b(seller|sell|list product|upload product)\b/.test(q)){
    return {
      text:"Create an account and choose Shopkeeper when signing up. Sellers can add products, specifications, prices, and stock from Shop Management."
    };
  }

  const terms=q.split(/[^a-z0-9]+/).filter(word=>
    word.length>2&&
    !["find","show","want","need","looking","for","some","product","products","please","recommend","suggest","something"].includes(word)
  );

  const matches=products
    .filter(product=>
      !productStock(product)&&
      terms.some(term=>
        [
          product.name,
          product.category,
          product.brand,
          product.description,
          product.color,
          product.size,
          ...Object.values(product.specifications||{})
        ].join(" ").toLowerCase().includes(term)
      )
    )
    .slice(0,3);

  if(matches.length){
    return {
      text:"These listed items may match what you’re looking for:",
      products:matches
    };
  }

  if(/\b(recommend|suggest|looking for|shop|browse)\b/.test(q)){
    const popular=products.filter(product=>!productStock(product)).slice(0,3);

    if(popular.length){
      return {
        text:"Here are a few available products to get you started:",
        products:popular
      };
    }
  }

  return {
    text:"I’m sorry, I couldn’t confidently solve that. Please contact customer support and they’ll help you directly.",
    contact:true
  };
}
document.getElementById("supportChatForm").addEventListener("submit",event=>{
  event.preventDefault();

  const input=document.getElementById("supportChatInput");
  const question=input.value.trim();

  if(!question)return;

  appendSupportMessage(question,"customer");
  input.value="";

  const answer=answerSupportQuestion(question);
  appendSupportMessage(answer.text,"assistant",answer);
});

document.getElementById("supportChatMessages").addEventListener("click",event=>{
  const productButton=event.target.closest("[data-support-product]");
  const voucherButton=event.target.closest("[data-support-voucher]");

  if(productButton){
    const product=products.find(item=>
      String(item.id)===productButton.dataset.supportProduct
    );

    if(product){
      closePanels();
      toast("Selected "+product.name);
      document.getElementById("products").scrollIntoView({
        behavior:"smooth"
      });
    }
  }

  if(voucherButton){
    const voucher=vouchers.find(item=>
      item.code===voucherButton.dataset.supportVoucher&&
      item.active&&
      (!item.membersOnly||isPlusMember())
    );

    if(voucher){
      appliedVoucher=voucher.code;
      localStorage.setItem("infinix-applied-voucher",appliedVoucher);
      saveCart();
      toast("Voucher selected: "+voucher.code);
    }
  }
});
