"""
A bit experimental script for training new models for tagging, parsing and lemmatization
TODO: Currently tokenizer must be trained manually from command line (for instructions see docs/training.md)

Parameters are obtained from templates/lemmatizer.yaml, templates/parser.cfg, templates/tagger.cfg, templates/tokenizer.cfg
--> By defaut it will use same parameters as in the TurkuNLP CoNLL-18 models, but you can change the hyperparameter settings in these files if you wish
"""

import os
import sys
import glob
from shutil import copyfile, rmtree
import re
from distutils.util import strtobool

from lemmatizer_mod import Lemmatizer, read_conllu

ID, FORM, LEMMA, UPOS, XPOS, FEATS, HEAD, DEPREL, DEPS, MISC = range(10)

thisdir=os.path.dirname(os.path.realpath(__file__))


def numeric_sort(x):
    r = re.compile('(\d+)')
    l = r.split(x)
    return [int(y) if y.isdigit() else y for y in l]


def copy_lemmatizer(args):

    files=glob.glob(f"{args.tmp}/lemmatizer_step_*.pt".format(name=args.name))
    latest=sorted(files, key =numeric_sort)[-1]
    copyfile(latest, f"{args.tmp}/lemmatizer.pt")


def create_dataset(fname):

    lemmatizer = Lemmatizer()
    data=[]
    with open(fname, "rt", encoding="utf-8") as f:
        for comm, sent in read_conllu(f):
            for token in sent:
                word, lemma = lemmatizer.transform_token(token)
                data.append((word, lemma))
                
    return data
    
def print_tmp(train, devel, path):

    with open(os.path.join(path, "train.input"), "wt", encoding="utf-8") as inpf, open(os.path.join(path, "train.output"), "wt", encoding="utf-8") as outf:
        for (word, lemma) in train:
            print(word, file=inpf)
            print(lemma, file=outf)
            
    with open(os.path.join(path, "devel.input"), "wt", encoding="utf-8") as inpf, open(os.path.join(path, "devel.output"), "wt", encoding="utf-8") as outf:
        for (word, lemma) in devel:
            print(word, file=inpf)
            print(lemma, file=outf)
            
            
def train_model(args):

    # data
    preprocess = f"onmt_preprocess -train_src {args.tmp}/train.input -train_tgt {args.tmp}/train.output -valid_src {args.tmp}/devel.input -valid_tgt {args.tmp}/devel.output -save_data {args.tmp}/preprocessed-data -src_words_min_frequency {args.min_char_freq} -tgt_words_min_frequency {args.min_char_freq} -overwrite"
    print(preprocess, file=sys.stderr)
    status = os.system(preprocess)
    if status != 0:
        print("Lemmatizer status:", status, "Preprocessing failed.", file=sys.stderr)
        sys.exit()
        
    # train model
    train = f"CUDA_VISIBLE_DEVICES={args.gpu} onmt_train -data {args.tmp}/preprocessed-data -save_model {args.tmp}/lemmatizer -gpu_ranks {args.gpu if args.gpu < 1 else 0} -learning_rate {args.lr} -batch_size {args.batch_size} -optim {args.optimizer} -learning_rate_decay {args.learning_rate_decay} -dropout {args.dropout} -encoder_type brnn -train_steps {args.train_steps} -save_checkpoint_steps {args.save_every_steps} -valid_steps {args.save_every_steps}"
    print(train, file=sys.stderr)
    status = os.system(train)
    if status != 0:
        print("Lemmatizer status:", status, "Training failed.", file=sys.stderr)
        sys.exit()

    copy_lemmatizer(args) # copy the latest lemmatizer under correct name

#    status = os.system("cat {train} | python3 {workdir}/../build_lemma_cache.py > models_{name}/Lemmatizer/lemma_cache.tsv".format(train=args.train_file, workdir=thisdir, name=args.name)) # build lemma cache
#    if status != 0:
#        print("Lemma cache status:", status, "Training failed.", file=sys.stderr)
#        sys.exit()

print("Training done", file=sys.stderr)


def train(args):

    lemmatizer = Lemmatizer()

    train_data = create_dataset(args.train_file)
    devel_data = create_dataset(args.devel_file)
    
    print_tmp(train_data, devel_data, args.tmp)
    
    train_model(args)
    
    
    












if __name__=="__main__":
    import argparse
    argparser = argparse.ArgumentParser(description='A script for training a lemmatizer')
    argparser.add_argument('--name', default="lemmatizer.pt", help='Model name')
    argparser.add_argument('--train_file', type=str, required=True, help='Training data file (conllu)')
    argparser.add_argument('--devel_file', type=str, required=True, help='Development data file (conllu)')
    argparser.add_argument('--tmp', type=str, default="tmp", help='Directory to place temporary files')
    argparser.add_argument('--min_char_freq', type=int, default=5, help='Minimum character frequency to keep (rest will be replaced with unknown)')
    argparser.add_argument('--gpu', type=int, default=0, help='GPU device (-1 for CPU)')
    argparser.add_argument('--dropout', type=float, default=0.3, help='Dropout')
    argparser.add_argument('--optimizer', type=str, default="adam", help='Optimizer (adam/sgd)')
    argparser.add_argument('--lr', type=float, default=0.0005, help='Learning rate')
    argparser.add_argument('--learning_rate_decay', type=float, default=0.9, help='Learning rate decay')
    argparser.add_argument('--batch_size', type=int, default=64, help='Batch size')
    argparser.add_argument('--train_steps', type=int, default=10000, help='')
    argparser.add_argument('--save_every_steps', type=int, default=1000, help='')
    
    

    args = argparser.parse_args()

    print(args, file=sys.stderr)

    try:
        if os.path.isdir(args.tmp):
            input(f'\nTemporary directory {args.tmp} already exists, old files will be deleted. Press <Enter> to continue or <Ctrl-c> to abort.\n'.format(name=args.name))
            files=[]
            for dirpath, dirnames, filenames in os.walk(args.tmp):
                for fname in filenames:
                    files.append(os.path.join(dirpath, fname))
            input('\nDeleting {files}. Press <Enter> to continue or <Ctrl-c> to abort.\n'.format(files=", ".join(files)))
            for f in files:
                print("Deleting",f,file=sys.stderr)
                os.remove(f)
        else:
            os.mkdir(args.tmp)
    except KeyboardInterrupt:
        print(file=sys.stderr)
        sys.exit(0)

    train(args)
