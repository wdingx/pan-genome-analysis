import os,sys,time; from collections import defaultdict,Counter
from SF00miscellaneous import times,load_pickle,read_fasta,write_pickle

def diamond_run(query_path, output_path, dmd_ref_file, dmd_query_file_prefix, threads):
    """ runn diamond using sensitive alignment mode """
    os.system('pwd')
    diam='./tools/diamond';
    print '# Run for %s.fna'%dmd_query_file_prefix
    start = time.time();
    os.system(diam+' makedb --in '+output_path+dmd_ref_file+' -d '+output_path+'nr');
    print 'build index:', times(start)

    start = time.time();
    os.system(diam+' blastp --sensitive -p '+str(threads)+' -k 600 -d '+output_path+'nr -q '+query_path+dmd_query_file_prefix+'.fna'+' -a '+output_path+dmd_query_file_prefix+'_matches -t ./');
    print 'matchin:', times(start)

    start = time.time();
    os.system(diam+' view -a  '+output_path+dmd_query_file_prefix+'_matches.daa -o '+output_path+dmd_query_file_prefix+'_matches.m8');
    print 'view:', times(start)
    os.system('rm '+output_path+'nr.dmnd; rm '+output_path+'*.daa')

def ortha_mcl_run(species,output_path):
    """ run orthAgogue and MCL """
    os.system("orthAgogue -i "+output_path+species+"_matches.m8 -s '|' -O "+output_path+species+"-ortha > "+output_path+"ortha-"+species+".log  2>&1")
    os.system('mv report_orthAgogue '+output_path)
    os.system('mv '+output_path+species+'-ortha/all.abc '+output_path)
    os.system('mcl '+output_path+'all.abc --abc -o '+output_path+species+'-orthamcl-cluster.output > '+output_path+'mcl-'+species+'.log 2>&1')

def orthagogue_singletons(path,species,origin_cluster_file,all_fna_file):
    """ add singletons from original MCL output """
    from operator import or_
    all_fna_file="%s%s"%(path,all_fna_file)
    origin_cluster_file="%s%s"%(path,origin_cluster_file)
    all_cluster_file="%s%s%s"%(path,species,'-orthamcal-allclusters.csv')

    # TODO: following not used?
    # orthagogue_set_dt=defaultdict(list)
    # loop over cluster_file, each line is one cluster tab delimited geneIDs (strain-locusTag)
    # generate union of all genes in all clusters excluding singletons
    with open(origin_cluster_file, 'rb') as infile:
        orthagogue_set=reduce(or_, [ set(iline.rstrip().split('\t')) for iline in infile ])

    # read all geneIDs from all genes from all strains, determine singletons as set difference
    all_fna_set=set( read_fasta(all_fna_file).keys() );
    singletons=all_fna_set-orthagogue_set
    print len(all_fna_set), len(orthagogue_set), len(singletons)

    # append singleton clusters to a copy of the original file
    os.system('cp '+origin_cluster_file+' '+all_cluster_file);
    with open(all_cluster_file, 'a') as outputfile:
        for isi in singletons:
            outputfile.write(isi+'\n')


def parse_geneCluster(path,species,inputfile):
    """ store clusters as dictionary in cpk file """
    from operator import itemgetter
    inputfile="%s%s"%(path,inputfile)
    with open(inputfile, 'rb') as infile:
        geneCluster_dt=defaultdict(list)
        for gid, iline in enumerate(infile): ##format: NC_022226|1-1956082:1956435
            col=iline.rstrip().split('\t')
            clusterID="GC_%08d"%gid
            geneCluster_dt[clusterID]=[0,[],0]
            ## num_stains
            geneCluster_dt[clusterID][0]=len(dict(Counter([ ivg.split('|')[0] for ivg in col])).keys())
            ## num_genes
            geneCluster_dt[clusterID][2]=len(dict(Counter([ ivg for ivg in col])).keys())
            ## gene members
            geneCluster_dt[clusterID][1]=[ icol for icol in col ]
    write_pickle(path+species+'-orthamcl-allclusters.cpk',geneCluster_dt)

    with open(path+species+'-orthamcl-allclusters.log', 'wb') as write_fn_lst:
        orthagogue_geneCount_lst=sorted( geneCluster_dt.iteritems(), key=itemgetter(1), reverse=True);
        for kd, vd in orthagogue_geneCount_lst:
            write_fn_lst.write('%s%s\n'%(kd, vd));

def diamond_orthamcl_cluster(path,species, threads, blast_file_path='none', cluster_file_path='none'):
    '''
    TODO expand and structure
    make all-against-all comparison using diamond
    OR use all-to-all blast comparison
    THEN generate gene clusters followed by orthoMCL/orthagogue
    OR use the output of roary
    params:
        path:       path to directory including data and output
        species:    prefix for output files
        threads:    number of parallel threads used to run diamond
        blast_file_path:
    '''
    input_path=path+'protein_fna/';
    output_path=input_path+'diamond_matches/';
    ## using standard pipeline (cluster_file_path=='none')
    if cluster_file_path=='none':
        if blast_file_path=='none':
            dmd_ref_file=species+'_enrich.faa'; dmd_query_file=species+'.fna'
            ## prepare dmd_query_file
            os.system('mkdir '+output_path)
            os.system('cat '+input_path+'*fna > '+output_path+dmd_query_file)
            ## dmd_query_file is dmd_ref_file
            os.system('cp '+output_path+dmd_query_file+' '+output_path+dmd_ref_file)
            diamond_run(output_path, output_path, dmd_ref_file, species, threads)
            ortha_mcl_run(species,output_path)
            ## save singeltons
            origin_cluster_file=species+'-orthamcl-cluster.output';
            orthagogue_singletons(output_path,species,origin_cluster_file,dmd_query_file)
            all_cluster_file=species+'-orthamcal-allclusters.csv';
            parse_geneCluster(output_path,species,all_cluster_file)
        else: ## using blast score
            os.system('mkdir %s'%output_path)
            os.system('ln -sf %s %sclustered_proteins'%(blast_file_path, output_path))
            from operator import itemgetter
            locusTag_to_geneId_Dt=load_pickle(path+'locusTag_to_geneId.cpk')
            ## create gene cluster from blast output
            with open(blast_file_path, 'rb') as infile:
                geneCluster_dt=defaultdict(list)
                for gid, iline in enumerate(infile):
                    column=iline.rstrip().split('\t')
                    clusterID="GC_%08d"%gid
                    gene_list=[ locusTag_to_geneId_Dt[ico] for ico in column ]
                    geneCluster_dt[clusterID]=[0,[],0]
                    num_stains=len( dict(Counter([ ivg.split('|')[0] for ivg in gene_list ])) )
                    num_gene=len(dict(Counter([ ivg for ivg in column])));
                    geneCluster_dt[ clusterID ][0]=num_stains
                    geneCluster_dt[ clusterID ][2]=num_gene
                    geneCluster_dt[ clusterID ][1]=gene_list
            write_pickle(output_path+species+'-orthamcl-allclusters.cpk', geneCluster_dt)

            orthagogue_geneCount_lst=sorted( geneCluster_dt.iteritems(), key=itemgetter(1), reverse=True)
            with open(output_path+species+'-orthamcl-allclusters.log', 'wb') as write_fn_lst:
                for kd, vd in orthagogue_geneCount_lst:
                    write_fn_lst.write('%s%s\n'%(kd, vd))
    else: ## using cluster files from roary
        os.system('mkdir %s'%output_path)
        os.system('ln -sf %s %sclustered_proteins'%(cluster_file_path, output_path))
        locusTag_to_geneId_Dt=load_pickle(path+'locusTag_to_geneId.cpk')
        with open(cluster_file_path, 'rb') as cluster_external_file:
            with open(output_path+species+'-orthamcl-allclusters.csv', 'wb') as cluster_final_file:
                for cluster_line in cluster_external_file:
                     cluster_final_file.write( '%s\n'%'\t'.join([ locusTag_to_geneId_Dt[gene_tag] for gene_tag in cluster_line.rstrip().split(': ')[1].split('\t')]) )
        all_cluster_file=species+'-orthamcl-allclusters.csv';
        parse_geneCluster(output_path,species,all_cluster_file)
