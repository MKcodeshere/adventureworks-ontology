-- Scrambled warehouse layer over AdventureWorks.
-- Cryptic names mimic a real warehouse. Mapping lives in data/scramble_map.yaml (debug only).

CREATE SCHEMA IF NOT EXISTS wh;

-- Sales orders
CREATE OR REPLACE VIEW wh.sls_ord_hdr AS
SELECT
  salesorderid        AS ord_id,
  revisionnumber      AS rev_no,
  orderdate           AS ord_dt,
  duedate             AS due_dt,
  shipdate            AS ship_dt,
  status              AS stat_cd,
  onlineorderflag     AS onl_flg,
  purchaseordernumber AS po_no,
  accountnumber       AS acct_no,
  customerid          AS cst_id,
  salespersonid       AS rep_id,
  territoryid         AS terr_id,
  billtoaddressid     AS bill_addr_id,
  shiptoaddressid     AS ship_addr_id,
  shipmethodid        AS ship_mthd_id,
  creditcardid        AS cc_id,
  creditcardapprovalcode AS cc_appr_cd,
  currencyrateid      AS fx_id,
  subtotal            AS sub_amt,
  taxamt              AS tax_amt,
  freight             AS frt_amt,
  totaldue            AS net_amt,
  comment             AS cmt_txt,
  rowguid             AS row_guid,
  modifieddate        AS mod_dt
FROM sales.salesorderheader;

CREATE OR REPLACE VIEW wh.sls_ord_dtl AS
SELECT
  salesorderid       AS ord_id,
  salesorderdetailid AS dtl_id,
  carriertrackingnumber AS trk_no,
  orderqty           AS qty,
  productid          AS prd_id,
  specialofferid     AS ofr_id,
  unitprice          AS unit_prc,
  unitpricediscount  AS disc_pct,
  rowguid            AS row_guid,
  modifieddate       AS mod_dt
FROM sales.salesorderdetail;

CREATE OR REPLACE VIEW wh.cst_mstr AS
SELECT
  customerid    AS cst_id,
  personid      AS pers_id,
  storeid       AS str_id,
  territoryid   AS terr_id,
  rowguid       AS row_guid,
  modifieddate  AS mod_dt
FROM sales.customer;

CREATE OR REPLACE VIEW wh.str_mstr AS
SELECT
  businessentityid AS str_id,
  name             AS str_nm,
  salespersonid    AS rep_id,
  demographics     AS demo_xml,
  rowguid          AS row_guid,
  modifieddate     AS mod_dt
FROM sales.store;

CREATE OR REPLACE VIEW wh.terr_dim AS
SELECT
  territoryid       AS terr_id,
  name              AS terr_nm,
  countryregioncode AS ctry_cd,
  "group"           AS terr_grp,
  salesytd          AS sls_ytd,
  saleslastyear     AS sls_ly,
  costytd           AS cost_ytd,
  costlastyear      AS cost_ly,
  rowguid           AS row_guid,
  modifieddate      AS mod_dt
FROM sales.salesterritory;

CREATE OR REPLACE VIEW wh.sls_rep AS
SELECT
  businessentityid AS rep_id,
  territoryid      AS terr_id,
  salesquota       AS quota_amt,
  bonus            AS bonus_amt,
  commissionpct    AS comm_pct,
  salesytd         AS sls_ytd,
  saleslastyear    AS sls_ly,
  rowguid          AS row_guid,
  modifieddate     AS mod_dt
FROM sales.salesperson;

CREATE OR REPLACE VIEW wh.spec_ofr AS
SELECT
  specialofferid AS ofr_id,
  description    AS ofr_desc,
  discountpct    AS disc_pct,
  type           AS ofr_typ,
  category       AS ofr_cat,
  startdate      AS start_dt,
  enddate        AS end_dt,
  minqty         AS min_qty,
  maxqty         AS max_qty,
  rowguid        AS row_guid,
  modifieddate   AS mod_dt
FROM sales.specialoffer;

CREATE OR REPLACE VIEW wh.spec_ofr_prd AS
SELECT
  specialofferid AS ofr_id,
  productid      AS prd_id,
  rowguid        AS row_guid,
  modifieddate   AS mod_dt
FROM sales.specialofferproduct;

CREATE OR REPLACE VIEW wh.sls_rsn AS
SELECT
  salesreasonid AS rsn_id,
  name          AS rsn_nm,
  reasontype    AS rsn_typ,
  modifieddate  AS mod_dt
FROM sales.salesreason;

CREATE OR REPLACE VIEW wh.sls_ord_rsn AS
SELECT
  salesorderid  AS ord_id,
  salesreasonid AS rsn_id,
  modifieddate  AS mod_dt
FROM sales.salesorderheadersalesreason;

-- Products
CREATE OR REPLACE VIEW wh.prd_mstr AS
SELECT
  productid             AS prd_id,
  name                  AS prd_nm,
  productnumber         AS prd_no,
  makeflag              AS make_flg,
  finishedgoodsflag     AS fg_flg,
  color                 AS clr_cd,
  safetystocklevel      AS safe_stk,
  reorderpoint          AS reord_pt,
  standardcost          AS std_cost,
  listprice             AS list_prc,
  size                  AS size_cd,
  sizeunitmeasurecode   AS size_uom,
  weightunitmeasurecode AS wt_uom,
  weight                AS wt_val,
  daystomanufacture     AS mfg_days,
  productline           AS line_cd,
  class                 AS cls_cd,
  style                 AS style_cd,
  productsubcategoryid  AS subcat_id,
  productmodelid        AS mdl_id,
  sellstartdate         AS sell_start_dt,
  sellenddate           AS sell_end_dt,
  discontinueddate      AS disc_dt,
  rowguid               AS row_guid,
  modifieddate          AS mod_dt
FROM production.product;

CREATE OR REPLACE VIEW wh.prd_subcat AS
SELECT
  productsubcategoryid AS subcat_id,
  productcategoryid    AS cat_id,
  name                 AS subcat_nm,
  rowguid              AS row_guid,
  modifieddate         AS mod_dt
FROM production.productsubcategory;

CREATE OR REPLACE VIEW wh.prd_cat AS
SELECT
  productcategoryid AS cat_id,
  name              AS cat_nm,
  rowguid           AS row_guid,
  modifieddate      AS mod_dt
FROM production.productcategory;

CREATE OR REPLACE VIEW wh.prd_mdl AS
SELECT
  productmodelid     AS mdl_id,
  name               AS mdl_nm,
  catalogdescription AS catlg_xml,
  instructions       AS instr_xml,
  rowguid            AS row_guid,
  modifieddate       AS mod_dt
FROM production.productmodel;

CREATE OR REPLACE VIEW wh.prd_desc AS
SELECT
  productdescriptionid AS desc_id,
  description          AS desc_txt,
  rowguid              AS row_guid,
  modifieddate         AS mod_dt
FROM production.productdescription;

CREATE OR REPLACE VIEW wh.prd_mdl_desc_cult AS
SELECT
  productmodelid       AS mdl_id,
  productdescriptionid AS desc_id,
  cultureid            AS cult_cd,
  modifieddate         AS mod_dt
FROM production.productmodelproductdescriptionculture;

CREATE OR REPLACE VIEW wh.prd_rev AS
SELECT
  productreviewid AS rev_id,
  productid       AS prd_id,
  reviewername    AS rev_nm,
  reviewdate      AS rev_dt,
  emailaddress    AS email,
  rating          AS rating_val,
  comments        AS cmt_txt,
  modifieddate    AS mod_dt
FROM production.productreview;

CREATE OR REPLACE VIEW wh.bom AS
SELECT
  billofmaterialsid AS bom_id,
  productassemblyid AS asm_prd_id,
  componentid       AS cmp_prd_id,
  startdate         AS start_dt,
  enddate           AS end_dt,
  unitmeasurecode   AS uom_cd,
  bomlevel          AS bom_lvl,
  perassemblyqty    AS qty_per,
  modifieddate      AS mod_dt
FROM production.billofmaterials;

CREATE OR REPLACE VIEW wh.wrk_ord AS
SELECT
  workorderid   AS wrk_id,
  productid     AS prd_id,
  orderqty      AS qty,
  scrappedqty   AS scrap_qty,
  startdate     AS start_dt,
  enddate       AS end_dt,
  duedate       AS due_dt,
  scrapreasonid AS scrap_rsn_id,
  modifieddate  AS mod_dt
FROM production.workorder;

CREATE OR REPLACE VIEW wh.doc_mstr AS
SELECT
  title          AS doc_title,
  owner          AS owner_id,
  folderflag     AS folder_flg,
  filename       AS file_nm,
  fileextension  AS file_ext,
  revision       AS rev_no,
  changenumber   AS chg_no,
  status         AS stat_cd,
  documentsummary AS summary_txt,
  rowguid        AS row_guid,
  modifieddate   AS mod_dt
FROM production.document;

-- People / HR
CREATE OR REPLACE VIEW wh.pers_mstr AS
SELECT
  businessentityid AS pers_id,
  persontype       AS pers_typ,
  namestyle        AS nm_style,
  title            AS title_cd,
  firstname        AS first_nm,
  middlename       AS mid_nm,
  lastname         AS last_nm,
  suffix           AS suffix_cd,
  emailpromotion   AS email_promo,
  additionalcontactinfo AS addl_xml,
  demographics     AS demo_xml,
  rowguid          AS row_guid,
  modifieddate     AS mod_dt
FROM person.person;

CREATE OR REPLACE VIEW wh.emp_mstr AS
SELECT
  businessentityid  AS emp_id,
  nationalidnumber  AS natl_id,
  loginid           AS login_id,
  jobtitle          AS job_title,
  birthdate         AS birth_dt,
  maritalstatus     AS mar_cd,
  gender            AS gndr_cd,
  hiredate          AS hire_dt,
  salariedflag      AS sal_flg,
  vacationhours     AS vac_hrs,
  sickleavehours    AS sick_hrs,
  currentflag       AS cur_flg,
  rowguid           AS row_guid,
  modifieddate      AS mod_dt,
  organizationnode  AS org_node
FROM humanresources.employee;

CREATE OR REPLACE VIEW wh.dept_mstr AS
SELECT
  departmentid AS dept_id,
  name         AS dept_nm,
  groupname    AS grp_nm,
  modifieddate AS mod_dt
FROM humanresources.department;

CREATE OR REPLACE VIEW wh.emp_dept_hist AS
SELECT
  businessentityid AS emp_id,
  departmentid     AS dept_id,
  shiftid          AS shift_id,
  startdate        AS start_dt,
  enddate          AS end_dt,
  modifieddate     AS mod_dt
FROM humanresources.employeedepartmenthistory;

CREATE OR REPLACE VIEW wh.addr_mstr AS
SELECT
  addressid       AS addr_id,
  addressline1    AS line1,
  addressline2    AS line2,
  city            AS city_nm,
  stateprovinceid AS st_id,
  postalcode      AS zip_cd,
  spatiallocation AS geo_loc,
  rowguid         AS row_guid,
  modifieddate    AS mod_dt
FROM person.address;

CREATE OR REPLACE VIEW wh.be_addr AS
SELECT
  businessentityid AS be_id,
  addressid        AS addr_id,
  addresstypeid    AS addr_typ_id,
  rowguid          AS row_guid,
  modifieddate     AS mod_dt
FROM person.businessentityaddress;

CREATE OR REPLACE VIEW wh.st_prov AS
SELECT
  stateprovinceid     AS st_id,
  stateprovincecode   AS st_cd,
  countryregioncode   AS ctry_cd,
  isonlystateprovinceflag AS only_flg,
  name                AS st_nm,
  territoryid         AS terr_id,
  rowguid             AS row_guid,
  modifieddate        AS mod_dt
FROM person.stateprovince;

CREATE OR REPLACE VIEW wh.ctry_rgn AS
SELECT
  countryregioncode AS ctry_cd,
  name              AS ctry_nm,
  modifieddate      AS mod_dt
FROM person.countryregion;

-- Purchasing
CREATE OR REPLACE VIEW wh.vnd_mstr AS
SELECT
  businessentityid AS vnd_id,
  accountnumber    AS acct_no,
  name             AS vnd_nm,
  creditrating     AS cred_rtg,
  preferredvendorstatus AS pref_flg,
  activeflag       AS act_flg,
  purchasingwebserviceurl AS ws_url,
  modifieddate     AS mod_dt
FROM purchasing.vendor;

CREATE OR REPLACE VIEW wh.po_hdr AS
SELECT
  purchaseorderid AS po_id,
  revisionnumber  AS rev_no,
  status          AS stat_cd,
  employeeid      AS emp_id,
  vendorid        AS vnd_id,
  shipmethodid    AS ship_mthd_id,
  orderdate       AS ord_dt,
  shipdate        AS ship_dt,
  subtotal        AS sub_amt,
  taxamt          AS tax_amt,
  freight         AS frt_amt,
  (subtotal + taxamt + freight) AS net_amt,
  modifieddate    AS mod_dt
FROM purchasing.purchaseorderheader;

CREATE OR REPLACE VIEW wh.cult_dim AS
SELECT cultureid AS cult_cd, name AS cult_nm, modifieddate AS mod_dt
FROM production.culture;

CREATE OR REPLACE VIEW wh.ship_mthd AS
SELECT shipmethodid AS ship_mthd_id, name AS ship_nm, shipbase AS base_amt,
       shiprate AS rate_amt, rowguid AS row_guid, modifieddate AS mod_dt
FROM purchasing.shipmethod;

CREATE OR REPLACE VIEW wh.po_dtl AS
SELECT
  purchaseorderid       AS po_id,
  purchaseorderdetailid AS dtl_id,
  duedate               AS due_dt,
  orderqty              AS qty,
  productid             AS prd_id,
  unitprice             AS unit_prc,
  receivedqty           AS rcv_qty,
  rejectedqty           AS rej_qty,
  modifieddate          AS mod_dt
FROM purchasing.purchaseorderdetail;

-- Helpful comment
COMMENT ON SCHEMA wh IS 'Scrambled warehouse layer for ontology tutorial. Cryptic names on purpose.';
